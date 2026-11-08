from pathlib import Path
import time
import threading

from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from truthtable import TEXT_PANEL_TRUTH, to_8bit

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="eeky808")

static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ---------- HOMEPAGE ----------
@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    context = {
        "request": request,
        "title": "eeky808",
        "heading": "eeky808",
        "tagline": "my build logic site or whatever",
        "intro": "made this cuz im obsessed with build logic on roblox lol",
    }
    return templates.TemplateResponse(request, "index.html", context)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tool", response_class=HTMLResponse)
def tool_page(request: Request):
    context = {"request": request, "title": "text panel tool - eeky808"}
    return templates.TemplateResponse(request, "tool.html", context)

@app.get("/truthtable", response_class=HTMLResponse)
def truthtable_page(request: Request):
    context = {"request": request, "title": "truth table - eeky808"}
    return templates.TemplateResponse(request, "truthtable.html", context)

# ---------- APIs ----------
api = APIRouter(prefix="/api")

class Item(BaseModel):
    name: str
    price: float
    is_offer: Optional[bool] = None

@api.get("/hello")
def hello():
    return {"message": "Hello from the API!"}

@api.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None):
    return {"item_id": item_id, "q": q}

@api.post("/items/")
def create_item(item: Item):
    return {"item_name": item.name, "item_price": item.price, "received": True}

# ---------- Alphabet lookup ----------
_ALPHABET: dict = {}
for _shift, _i5, _i4, _i3, _i2, _i1, _i0, _char in TEXT_PANEL_TRUTH:
    if _char == "":
        continue
    if _char in _ALPHABET:
        continue
    _ALPHABET[_char] = {"value": to_8bit(_shift, _i5, _i4, _i3, _i2, _i1, _i0)}

_SPACE_VALUE = _ALPHABET[" "]["value"]      # 00111111
_NOTHING_VALUE = "10000000"                  # idle — MSB=1
_NO_STORE = {"Cache-Control": "no-store"}

# ---------- Text Panel endpoints ----------
@api.get("/txtpanel", operation_id="txtpanel_all")
def txtpanel_all():
    return JSONResponse(_ALPHABET, headers=_NO_STORE)

@api.get("/txtpanel/table", operation_id="txtpanel_table")
def txtpanel_table():
    return JSONResponse([{"value": o["value"]} for o in _ALPHABET.values()], headers=_NO_STORE)

@api.get("/txtpanel/full", operation_id="txtpanel_full")
def txtpanel_full():
    return JSONResponse(
        [
            {
                "shift": shift, "i5": i5, "i4": i4, "i3": i3,
                "i2": i2, "i1": i1, "i0": i0,
                "char": char, "value": to_8bit(shift, i5, i4, i3, i2, i1, i0),
            }
            for shift, i5, i4, i3, i2, i1, i0, char in TEXT_PANEL_TRUTH
        ],
        headers=_NO_STORE,
    )

@api.get("/txtpanel/current", operation_id="txtpanel_current")
def txtpanel_current():
    if not _ALPHABET:
        return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)
    chars = list(_ALPHABET.keys())
    return JSONResponse(_ALPHABET[chars[int(time.time()) % len(chars)]], headers=_NO_STORE)

_HELLO_WORLD = "Hello World! "
_HELLO_INTERVAL = 0.5

@api.get("/txtpanel/hello", operation_id="txtpanel_hello")
def txtpanel_hello():
    ticks_per_sec = max(1, round(1 / _HELLO_INTERVAL))
    idx = int(time.time() * ticks_per_sec) % len(_HELLO_WORLD)
    entry = _ALPHABET.get(_HELLO_WORLD[idx])
    return JSONResponse(entry or {"value": _NOTHING_VALUE}, headers=_NO_STORE)

@api.get("/txtpanel/inputs/{char}", operation_id="txtpanel_inputs")
def txtpanel_inputs(char: str):
    if char not in _ALPHABET:
        raise HTTPException(status_code=404, detail=f"Character {char!r} not in truth table")
    for shift, i5, i4, i3, i2, i1, i0, c in TEXT_PANEL_TRUTH:
        if c == char and c != "":
            return {
                "char": char,
                "value": to_8bit(shift, i5, i4, i3, i2, i1, i0),
                "inputs": {"1": i5, "2": i4, "3": i3, "4": i2, "5": i1, "6": i0, "7": shift},
            }
    raise HTTPException(status_code=404, detail=f"Character {char!r} not found")

@api.get("/txtpanel/nothing", operation_id="txtpanel_nothing")
def txtpanel_nothing():
    return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)

@api.get("/txtpanel/{char}", operation_id="txtpanel_char")
def txtpanel_char(char: str):
    if char in _ALPHABET:
        return {"char": char, **_ALPHABET[char]}
    raise HTTPException(status_code=404, detail=f"Character {char!r} not in truth table")

# ---------- Typewriter ----------
_TYPEWRITER_LOCK = threading.Lock()
_TYPEWRITER_STATE = {
    "text": "type on the site lol",
    "pos": 0,
    "padding": "",
    "pending_space": False,
    "last_served_value": None,
    "last_served_char": None,
    "last_served_at": 0.0,
    "last_visible_char": None,     # last non-idle char — panel holds this on screen
    "last_visible_value": None,
}

def _char_to_value(ch: str) -> str:
    entry = _ALPHABET.get(ch)
    return entry["value"] if entry else _SPACE_VALUE

class TypewriterBody(BaseModel):
    text: str

@api.post("/typewriter", operation_id="typewriter_set")
def typewriter_set(body: TypewriterBody):
    text = body.text[:499]
    with _TYPEWRITER_LOCK:
        was_idle = not _TYPEWRITER_STATE["text"]
        _TYPEWRITER_STATE["text"] = text
        _TYPEWRITER_STATE["pos"] = 0
        _TYPEWRITER_STATE["pending_space"] = was_idle and bool(text)
    return JSONResponse({"status": "ok", "length": len(text)}, headers=_NO_STORE)

@api.get("/typewriter/current", operation_id="typewriter_current")
def typewriter_current():
    with _TYPEWRITER_LOCK:
        text = _TYPEWRITER_STATE["text"]
        if not text:
            value = _NOTHING_VALUE
            char = None
            # do NOT touch last_visible_* — panel still shows the previous char
        elif _TYPEWRITER_STATE["pending_space"]:
            _TYPEWRITER_STATE["pending_space"] = False
            value = _SPACE_VALUE
            char = " "
            _TYPEWRITER_STATE["last_visible_char"] = char
            _TYPEWRITER_STATE["last_visible_value"] = value
        else:
            buffer = text + _TYPEWRITER_STATE["padding"]
            pos = _TYPEWRITER_STATE["pos"]
            char = buffer[pos]
            value = _char_to_value(char)
            _TYPEWRITER_STATE["last_visible_char"] = char
            _TYPEWRITER_STATE["last_visible_value"] = value
            _TYPEWRITER_STATE["pos"] = pos + 1
            if _TYPEWRITER_STATE["pos"] >= len(buffer):
                _TYPEWRITER_STATE["text"] = ""
                _TYPEWRITER_STATE["pos"] = 0

        _TYPEWRITER_STATE["last_served_value"] = value
        _TYPEWRITER_STATE["last_served_char"] = char
        _TYPEWRITER_STATE["last_served_at"] = time.time()

    return JSONResponse({"value": value}, headers=_NO_STORE)

@api.get("/typewriter/status", operation_id="typewriter_status")
def typewriter_status():
    with _TYPEWRITER_LOCK:
        text = _TYPEWRITER_STATE["text"]
        pos = _TYPEWRITER_STATE["pos"]
        pending = _TYPEWRITER_STATE["pending_space"]
        last_at = _TYPEWRITER_STATE["last_served_at"]
        visible_char = _TYPEWRITER_STATE["last_visible_char"]
        visible_value = _TYPEWRITER_STATE["last_visible_value"]

    now = time.time()
    panel_active = last_at > 0 and (now - last_at) < 2.0
    since_last = round(now - last_at, 2) if last_at > 0 else None

    return JSONResponse({
        "text": text,
        "length": len(text),
        "pos": pos,
        "buffer_length": len(text),
        "panel_active": panel_active,
        "since_last_served": since_last,
        "panel_char": visible_char,
        "panel_value": visible_value,
        "pending_space": pending,
        "special": {"space": _SPACE_VALUE, "nothing": _NOTHING_VALUE},
    }, headers=_NO_STORE)

@api.post("/typewriter/clear", operation_id="typewriter_clear")
def typewriter_clear():
    with _TYPEWRITER_LOCK:
        _TYPEWRITER_STATE["text"] = ""
        _TYPEWRITER_STATE["pos"] = 0
        _TYPEWRITER_STATE["pending_space"] = False
        _TYPEWRITER_STATE["last_visible_char"] = None
        _TYPEWRITER_STATE["last_visible_value"] = None
    return JSONResponse({"status": "cleared"}, headers=_NO_STORE)

app.include_router(api)
