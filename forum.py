"""Forum backend: Postgres (Neon) version."""
import os
import re
import time
import html as html_lib
import hashlib
import secrets
import asyncio
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, quote

import asyncpg
import httpx
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(prefix="/forum")
api_router = APIRouter(prefix="/api/forum")

_SESSION_COOKIE = "forum_token"
_SESSION_TTL = 60 * 60 * 24 * 7
_PAGE_SIZE = 20

# ---------- Connection pool ----------
_pool: Optional[asyncpg.Pool] = None
_init_lock = asyncio.Lock()


def _parse_dsn(raw: str):
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    sslmode = qs.get("sslmode", [""])[0]
    needs_ssl = sslmode in ("require", "verify-ca", "verify-full")
    clean = urlunparse(parsed._replace(query=""))
    return clean, needs_ssl


async def _ensure_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _init_lock:
        if _pool is not None:
            return _pool
        raw = os.getenv("DATABASE_URL", "")
        if not raw:
            raise RuntimeError("DATABASE_URL env var not set")
        clean_dsn, needs_ssl = _parse_dsn(raw)
        _pool = await asyncpg.create_pool(
            dsn=clean_dsn,
            min_size=1,
            max_size=5,
            ssl="require" if needs_ssl else None,
            command_timeout=15,
        )
        await _init_schema(_pool)
        return _pool


async def _init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                banned BOOLEAN NOT NULL DEFAULT FALSE,
                created_at DOUBLE PRECISION NOT NULL
            );
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx
            ON users (LOWER(username));
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at DOUBLE PRECISION NOT NULL
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                image_url TEXT,
                author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                pinned BOOLEAN NOT NULL DEFAULT FALSE,
                locked BOOLEAN NOT NULL DEFAULT FALSE,
                flagged INTEGER NOT NULL DEFAULT 0,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS replies (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                image_url TEXT,
                author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL
            );
        """)
        # user tags (added later — ALTER for existing DBs)
       await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tag_text TEXT;")
       await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tag_color_1 TEXT;")
       await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tag_color_2 TEXT;")


# ---------- Auth ----------
_session_cache = {}
_CACHE_TTL = 30


def _hash_pw(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100_000).hex()


async def _create_user(pool, username: str, password: str, role: str = "user") -> dict:
    if not re.match(r"^[A-Za-z0-9_]{3,20}$", username):
        raise HTTPException(400, "username: 3-20 letters, numbers, underscore only")
    if len(password) < 6:
        raise HTTPException(400, "password must be 6+ chars")
    salt = secrets.token_bytes(16)
    pw_hash = _hash_pw(password, salt)
    async with pool.acquire() as conn:
        try:
            uid = await conn.fetchval(
                "INSERT INTO users (username, password_hash, salt, role, banned, created_at) "
                "VALUES ($1, $2, $3, $4, FALSE, $5) RETURNING id",
                username, pw_hash, salt.hex(), role, time.time(),
            )
            return {"id": uid, "username": username, "role": role, "banned": False}
        except asyncpg.UniqueViolationError:
            raise HTTPException(400, "username already taken")


async def _verify_login(pool, username: str, password: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE LOWER(username) = LOWER($1)",
            username,
        )
    if not row:
        return None
    salt = bytes.fromhex(row["salt"])
    if _hash_pw(password, salt) != row["password_hash"]:
        return None
    return dict(row)


async def _create_session(pool, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES ($1, $2, $3)",
            token, user_id, time.time(),
        )
    return token


async def _current_user(request: Request, pool) -> Optional[dict]:
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    now = time.time()
    cached = _session_cache.get(token)
    if cached and (now - cached["at"]) < _CACHE_TTL:
        return cached["user"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id "
            "WHERE s.token = $1 AND s.created_at > $2",
            token, now - _SESSION_TTL,
        )
    if not row:
        _session_cache.pop(token, None)
        return None
    user = dict(row)
    _session_cache[token] = {"user": user, "at": now}
    return user


def _login_redirect(request: Request) -> RedirectResponse:
    next_url = request.url.path
    if request.url.query:
        next_url += "?" + request.url.query
    return RedirectResponse(f"/forum/login?next={quote(next_url)}", status_code=303)


def _set_session_cookie(response, token: str):
    response.set_cookie(
        _SESSION_COOKIE, token,
        max_age=_SESSION_TTL, httponly=True, samesite="lax", path="/",
    )


# ---------- Rich text render (safe) ----------
def render_rt(text: str) -> str:
    if not text:
        return ""
    s = html_lib.escape(text, quote=False)
    for src, dst in [
        ("&amp;lt;", "&lt;"), ("&amp;gt;", "&gt;"),
        ("&amp;quot;", "&quot;"), ("&amp;apos;", "&#39;"),
        ("&amp;amp;", "&amp;"),
    ]:
        s = s.replace(src, dst)
    s = re.sub(r"&lt;!--[\s\S]*?--&gt;", "", s)

    def _font(m):
        attrs = m.group(1)
        styles = []
        for key, css, tx in [
            ("color", "color", str),
            ("size", "font-size", lambda v: v + "px"),
            ("face", "font-family", str),
            ("weight", "font-weight", str),
        ]:
            cm = re.search(key + r'="([^"]+)"', attrs)
            if cm:
                styles.append(f"{css}:{tx(cm.group(1))}")
        tm = re.search(r'transparency="([\d.]+)"', attrs)
        if tm:
            styles.append(f"opacity:{max(0, 1 - float(tm.group(1)))}")
        return f'<span style="{";".join(styles)}">'

    s = re.sub(r"&lt;font\s+([^&]*?)&gt;", _font, s)
    s = s.replace("&lt;/font&gt;", "</span>")

    def _stroke(m):
        attrs = m.group(1)
        cm = re.search(r'color="([^"]+)"', attrs)
        tm = re.search(r'(?:thickness|th)="([\d.]+)"', attrs)
        return f'<span style="-webkit-text-stroke:{(tm.group(1) if tm else "1")}px {(cm.group(1) if cm else "#000")}">'

    s = re.sub(r"&lt;stroke\s+([^&]*?)&gt;", _stroke, s)
    s = s.replace("&lt;/stroke&gt;", "</span>")

    def _mark(m):
        attrs = m.group(1) or ""
        cm = re.search(r'color="([^"]+)"', attrs)
        return f'<span style="background-color:{(cm.group(1) if cm else "#ffff00")}">'

    s = re.sub(r"&lt;mark(?:\s+([^&]*?))?&gt;", _mark, s)
    s = s.replace("&lt;/mark&gt;", "</span>")

    for tag in ("b", "i", "u", "s"):
        s = s.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    s = re.sub(r"&lt;br\s*\/?&gt;", "<br>", s)

    for tag, css in [
        ("uppercase", "text-transform:uppercase"),
        ("uc", "text-transform:uppercase"),
        ("smallcaps", "font-variant:small-caps"),
        ("sc", "font-variant:small-caps"),
    ]:
        s = s.replace(f"&lt;{tag}&gt;", f'<span style="{css}">')
        s = s.replace(f"&lt;/{tag}&gt;", "</span>")

    s = re.sub(
        r"(https?://[^\s<>\"']+)",
        lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>',
        s,
    )
    return s


# ---------- Helpers ----------
def _sanitize_image_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "image url must start with http:// or https://")
    if len(url) > 2000:
        raise HTTPException(400, "image url too long")
    return url


async def _fetch_post(pool, post_id: int) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT p.*, u.username, u.role as author_role
            FROM posts p JOIN users u ON p.author_id = u.id
            WHERE p.id = $1
        """, post_id)
    return dict(row) if row else None


async def _fetch_replies(pool, post_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT r.*, u.username, u.role as author_role
            FROM replies r JOIN users u ON r.author_id = u.id
            WHERE r.post_id = $1
            ORDER BY r.created_at ASC
        """, post_id)
    return [dict(r) for r in rows]


def _ctx(request, user, **extra):
    base = {"request": request, "user": user, "title": "forum - eeky808"}
    base.update(extra)
    return base


# ---------- Auth routes ----------
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/forum"):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if user:
        return RedirectResponse(next, status_code=303)
    return templates.TemplateResponse(request, "forum_login.html",
        _ctx(request, None, next=next, mode="login"))


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, next: str = "/forum"):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if user:
        return RedirectResponse(next, status_code=303)
    return templates.TemplateResponse(request, "forum_login.html",
        _ctx(request, None, next=next, mode="register"))


@router.post("/register")
async def register(request: Request):
    pool = await _ensure_pool()
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    next_url = form.get("next") or "/forum"
    try:
        await _create_user(pool, username, password)
    except HTTPException as e:
        return templates.TemplateResponse(request, "forum_login.html",
            _ctx(request, None, error=e.detail, next=next_url, mode="register"),
            status_code=400)
    user = await _verify_login(pool, username, password)
    token = await _create_session(pool, user["id"])
    resp = RedirectResponse(next_url, status_code=303)
    _set_session_cookie(resp, token)
    return resp


@router.post("/login")
async def login(request: Request):
    pool = await _ensure_pool()
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    next_url = form.get("next") or "/forum"
    user = await _verify_login(pool, username, password)
    if not user:
        return templates.TemplateResponse(request, "forum_login.html",
            _ctx(request, None, error="wrong username or password", next=next_url, mode="login"),
            status_code=400)
    if user["banned"]:
        return templates.TemplateResponse(request, "forum_login.html",
            _ctx(request, None, error="you are banned", next=next_url, mode="login"),
            status_code=403)
    token = await _create_session(pool, user["id"])
    resp = RedirectResponse(next_url, status_code=303)
    _set_session_cookie(resp, token)
    return resp


@router.post("/logout")
async def logout(request: Request):
    pool = await _ensure_pool()
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        _session_cache.pop(token, None)
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE token = $1", token)
    resp = RedirectResponse("/forum", status_code=303)
    resp.delete_cookie(_SESSION_COOKIE, path="/")
    return resp


# ---------- Forum routes ----------
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def forum_index(request: Request, page: int = 1):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    page = max(1, page)
    offset = (page - 1) * _PAGE_SIZE
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM posts")
        rows = await conn.fetch("""
            SELECT p.*, u.username, u.role as author_role,
                   (SELECT COUNT(*) FROM replies WHERE post_id = p.id) as reply_count
            FROM posts p JOIN users u ON p.author_id = u.id
            ORDER BY p.pinned DESC, p.created_at DESC
            LIMIT $1 OFFSET $2
        """, _PAGE_SIZE, offset)
    posts = [dict(r) for r in rows]
    pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    return templates.TemplateResponse(request, "forum_index.html",
        _ctx(request, user, posts=posts, page=page, pages=pages, total=total))


@router.get("/new", response_class=HTMLResponse)
async def new_post_page(request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    return templates.TemplateResponse(request, "forum_new.html",
        _ctx(request, user, editing=False, post=None))


@router.post("/new")
async def new_post(request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    if user["banned"]:
        raise HTTPException(403, "you are banned")
    form = await request.form()
    title = (form.get("title") or "").strip()[:200]
    body = (form.get("body") or "").strip()[:10000]
    image_url = _sanitize_image_url(form.get("image_url"))
    if not title or not body:
        raise HTTPException(400, "title and body required")
    now = time.time()
    async with pool.acquire() as conn:
        post_id = await conn.fetchval(
            "INSERT INTO posts (title, body, image_url, author_id, pinned, locked, flagged, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, FALSE, FALSE, 0, $5, $6) RETURNING id",
            title, body, image_url, user["id"], now, now,
        )
    return RedirectResponse(f"/forum/post/{post_id}", status_code=303)


@router.get("/post/{post_id}", response_class=HTMLResponse)
async def view_post(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    post = await _fetch_post(pool, post_id)
    if not post:
        raise HTTPException(404, "post not found")
    replies = await _fetch_replies(pool, post_id)
    can_edit = bool(user and (user["id"] == post["author_id"] or user["role"] in ("mod", "admin")))
    can_mod = bool(user and user["role"] in ("mod", "admin"))
    return templates.TemplateResponse(request, "forum_post.html",
        _ctx(request, user, post=post, replies=replies,
             post_body_html=render_rt(post["body"]),
             replies_html=[{**r, "body_html": render_rt(r["body"])} for r in replies],
             can_edit=can_edit, can_mod=can_mod))


@router.post("/post/{post_id}/edit")
async def edit_post(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    post = await _fetch_post(pool, post_id)
    if not post:
        raise HTTPException(404)
    if user["id"] != post["author_id"] and user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "not your post")
    form = await request.form()
    title = (form.get("title") or "").strip()[:200]
    body = (form.get("body") or "").strip()[:10000]
    image_url = _sanitize_image_url(form.get("image_url"))
    if not title or not body:
        raise HTTPException(400, "title and body required")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET title = $1, body = $2, image_url = $3, updated_at = $4 WHERE id = $5",
            title, body, image_url, time.time(), post_id,
        )
    return RedirectResponse(f"/forum/post/{post_id}", status_code=303)


@router.post("/post/{post_id}/delete")
async def delete_post(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    post = await _fetch_post(pool, post_id)
    if not post:
        raise HTTPException(404)
    if user["id"] != post["author_id"] and user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "not your post")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM posts WHERE id = $1", post_id)
    return RedirectResponse("/forum", status_code=303)


@router.post("/post/{post_id}/pin")
async def pin_post(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user or user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "moderator only")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE posts SET pinned = NOT pinned WHERE id = $1", post_id)
    return RedirectResponse(f"/forum/post/{post_id}", status_code=303)


@router.post("/post/{post_id}/lock")
async def lock_post(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user or user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "moderator only")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE posts SET locked = NOT locked WHERE id = $1", post_id)
    return RedirectResponse(f"/forum/post/{post_id}", status_code=303)


@router.post("/post/{post_id}/flag")
async def flag_post(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE posts SET flagged = flagged + 1 WHERE id = $1", post_id)
    return RedirectResponse(f"/forum/post/{post_id}", status_code=303)


@router.post("/post/{post_id}/clear-flag")
async def clear_flag(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user or user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "moderator only")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE posts SET flagged = 0 WHERE id = $1", post_id)
    return RedirectResponse(f"/forum/post/{post_id}", status_code=303)


@router.post("/post/{post_id}/reply")
async def create_reply(post_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    if user["banned"]:
        raise HTTPException(403, "you are banned")
    post = await _fetch_post(pool, post_id)
    if not post:
        raise HTTPException(404)
    if post["locked"]:
        raise HTTPException(403, "post is locked")
    form = await request.form()
    body = (form.get("body") or "").strip()[:10000]
    image_url = _sanitize_image_url(form.get("image_url"))
    if not body:
        raise HTTPException(400, "reply body required")
    now = time.time()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO replies (post_id, body, image_url, author_id, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            post_id, body, image_url, user["id"], now, now,
        )
    return RedirectResponse(f"/forum/post/{post_id}#replies", status_code=303)


@router.post("/reply/{reply_id}/delete")
async def delete_reply(reply_id: int, request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        return _login_redirect(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM replies WHERE id = $1", reply_id)
    if not row:
        raise HTTPException(404)
    if user["id"] != row["author_id"] and user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "not your reply")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM replies WHERE id = $1", reply_id)
    return RedirectResponse(f"/forum/post/{row['post_id']}#replies", status_code=303)


# ---------- Mod panel ----------
@router.get("/mod", response_class=HTMLResponse)
async def mod_panel(request: Request):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user or user["role"] not in ("mod", "admin"):
        raise HTTPException(403, "moderator only")
    async with pool.acquire() as conn:
        flagged_rows = await conn.fetch("""
            SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id
            WHERE p.flagged > 0 ORDER BY p.flagged DESC, p.created_at DESC LIMIT 50
        """)
        user_rows = await conn.fetch(
            "SELECT id, username, role, banned, created_at FROM users ORDER BY created_at DESC"
        )
    return templates.TemplateResponse(request, "forum_mod.html",
        _ctx(request, user,
             flagged=[dict(r) for r in flagged_rows],
             users=[dict(r) for r in user_rows],
             is_admin=(user["role"] == "admin")))


@router.post("/user/{user_id}/ban")
async def ban_user(user_id: int, request: Request):
    pool = await _ensure_pool()
    mod = await _current_user(request, pool)
    if not mod or mod["role"] not in ("mod", "admin"):
        raise HTTPException(403, "moderator only")
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        if not row:
            raise HTTPException(404)
        if row["role"] == "admin" and mod["role"] != "admin":
            raise HTTPException(403, "can't ban an admin")
        await conn.execute("UPDATE users SET banned = NOT banned WHERE id = $1", user_id)
    _session_cache.clear()
    return RedirectResponse("/forum/mod", status_code=303)


@router.post("/user/{user_id}/role")
async def set_user_role(user_id: int, request: Request):
    pool = await _ensure_pool()
    admin = await _current_user(request, pool)
    if not admin or admin["role"] != "admin":
        raise HTTPException(403, "admin only")
    form = await request.form()
    new_role = form.get("role") or "user"
    if new_role not in ("user", "mod", "admin"):
        raise HTTPException(400, "invalid role")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET role = $1 WHERE id = $2", new_role, user_id)
    _session_cache.clear()
    return RedirectResponse("/forum/mod", status_code=303)


# ---------- Image upload (via catbox, no account needed) ----------
@api_router.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    pool = await _ensure_pool()
    user = await _current_user(request, pool)
    if not user:
        raise HTTPException(401, "login required")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "image too big (max 5 MB)")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (file.filename or "image.png", data, file.content_type or "image/png")},
        )
    if r.status_code >= 400 or not r.text.startswith("https://"):
        raise HTTPException(502, f"upload failed: {r.text[:200]}")
    return JSONResponse({"url": r.text.strip()})

# ---------- User tags (admin only) ----------
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@router.post("/user/{user_id}/tag")
async def set_user_tag(user_id: int, request: Request):
    pool = await _ensure_pool()
    admin = await _current_user(request, pool)
    if not admin or admin["role"] != "admin":
        raise HTTPException(403, "admin only")

    form = await request.form()
    tag_text = (form.get("tag_text") or "").strip()[:20]
    c1 = (form.get("tag_color_1") or "").strip()
    c2 = (form.get("tag_color_2") or "").strip()

    # empty tag = clear it
    if not tag_text:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET tag_text = NULL, tag_color_1 = NULL, tag_color_2 = NULL WHERE id = $1",
                user_id,
            )
        _session_cache.clear()
        return RedirectResponse("/forum/mod", status_code=303)

    if not _HEX_COLOR_RE.match(c1):
        raise HTTPException(400, "color 1 must be #rrggbb")
    if not _HEX_COLOR_RE.match(c2):
        raise HTTPException(400, "color 2 must be #rrggbb")

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
        if not row:
            raise HTTPException(404, "user not found")
        await conn.execute(
            "UPDATE users SET tag_text = $1, tag_color_1 = $2, tag_color_2 = $3 WHERE id = $4",
            tag_text, c1.lower(), c2.lower(), user_id,
        )
    _session_cache.clear()
    return RedirectResponse("/forum/mod", status_code=303)


@router.post("/user/{user_id}/clear-tag")
async def clear_user_tag(user_id: int, request: Request):
    pool = await _ensure_pool()
    admin = await _current_user(request, pool)
    if not admin or admin["role"] != "admin":
        raise HTTPException(403, "admin only")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET tag_text = NULL, tag_color_1 = NULL, tag_color_2 = NULL WHERE id = $1",
            user_id,
        )
    _session_cache.clear()
    return RedirectResponse("/forum/mod", status_code=303)
