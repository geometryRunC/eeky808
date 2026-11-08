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

# ---------- Static files & templates ----------
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

@app.get("/debug/files")
def debug_files():
    import os
    src = "/opt/render/project/src"
    result = {"cwd": os.getcwd(), "root": sorted(os.listdir(src))}
    tpl = os.path.join(src, "templates")
    result["templates"] = sorted(os.listdir(tpl)) if os.path.isdir(tpl) else "MISSING"
    return result

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
    return {
        "item_name": item.name,
        "item_price": item.price,
        "received": True,
    }

# ---------- Alphabet lookup (built from truth table) ----------
_ALPHABET: dict = {}
for _shift, _i5, _i4, _i3, _i2, _i1, _i0, _char in TEXT_PANEL_TRUTH:
    if _char == "":
        continue
    if _char in _ALPHABET:
        continue
    _ALPHABET[_char] = {"value": to_8bit(_shift, _i5, _i4, _i3, _i2, _i1, _i0)}

_NO_STORE = {"Cache-Control": "no-store"}

# ---------- Text Panel endpoints ----------
# IMPORTANT: specific routes FIRST, dynamic /{char} LAST.

@api.get("/txtpanel", operation_id="txtpanel_all")
def txtpanel_all():
    """Full map: {char: {"value": "8-bit"}} (deduped, empties skipped)."""
    return JSONResponse(_ALPHABET, headers=_NO_STORE)

@api.get("/txtpanel/table", operation_id="txtpanel_table")
def txtpanel_table():
    """Deduped truth table as ordered list of {value: "8-bit"} entries."""
    return JSONResponse(
        [{"value": obj["value"]} for obj in _ALPHABET.values()],
        headers=_NO_STORE,
    )

@api.get("/txtpanel/full", operation_id="txtpanel_full")
def txtpanel_full():
    """Raw truth table: shift/i5…i0/char/value per row (128 rows, nothing skipped)."""
    return JSONResponse(
        [
            {
                "shift": shift, "i5": i5, "i4": i4, "i3": i3,
                "i2": i2, "i1": i1, "i0": i0,
                "char": char,
                "value": to_8bit(shift, i5, i4, i3, i2, i1, i0),
            }
            for shift, i5, i4, i3, i2, i1, i0, char in TEXT_PANEL_TRUTH
        ],
        headers=_NO_STORE,
    )

@api.get("/txtpanel/current", operation_id="txtpanel_current")
def txtpanel_current():
    """Current character's 8-bit value — advances once per wall-clock second."""
    if not _ALPHABET:
        return JSONResponse({"value": "00000000"}, headers=_NO_STORE)
    chars = list(_ALPHABET.keys())
    idx = int(time.time()) % len(chars)
    return JSONResponse(_ALPHABET[chars[idx]], headers=_NO_STORE)

# ---------- "Hello World!" cycler ----------
_HELLO_WORLD = "Hello World! "
_HELLO_INTERVAL = 0.5

@api.get("/txtpanel/hello", operation_id="txtpanel_hello")
def txtpanel_hello():
    """Cycles through 'Hello World! ' every _HELLO_INTERVAL seconds."""
    ticks_per_sec = max(1, round(1 / _HELLO_INTERVAL))
    idx = int(time.time() * ticks_per_sec) % len(_HELLO_WORLD)
    entry = _ALPHABET.get(_HELLO_WORLD[idx])
    return JSONResponse(entry or {"value": "00000000"}, headers=_NO_STORE)

# Dynamic catch-all MUST come after /current, /table, /full, /hello
@api.get("/txtpanel/{char}", operation_id="txtpanel_char")
def txtpanel_char(char: str):
    """Look up a single character's 8-bit value."""
    if char in _ALPHABET:
        return {"char": char, **_ALPHABET[char]}
    raise HTTPException(status_code=404, detail=f"Character {char!r} not in truth table")

# ---------- Mount router AFTER all routes are defined ----------
app.include_router(api)

# ---------- Panel: Bad Apple 16×16 ----------
_BADAPPLE_BIN = BASE_DIR / "badapple16.bin"

def _load_badapple_bin() -> list[str]:
    """Load 256-bit frames from badapple16.bin. Fails fast if missing."""
    if not _BADAPPLE_BIN.is_file():
        raise RuntimeError(
            f"badapple16.bin not found at {_BADAPPLE_BIN}. "
            f"Run gen_badapple.py to create it, then commit the file."
        )
    with open(_BADAPPLE_BIN) as f:
        frames = [ln.strip() for ln in f if len(ln.strip()) == 256]
    if not frames:
        raise RuntimeError(
            f"{_BADAPPLE_BIN} exists but contains no valid 256-bit frame lines."
        )
    print(f"[badapple] loaded {len(frames)} frames from {_BADAPPLE_BIN.name}")
    return frames

_BADAPPLE_FRAMES = _load_badapple_bin()

_BADAPPLE_COUNTER = 0
_BADAPPLE_COUNTER_LOCK = threading.Lock()

@app.get("/panel/badapple16", operation_id="panel_badapple16")
def panel_badapple16():
    """
    Bad Apple!! at 16×16.
    Each GET advances to the NEXT frame (counter-based, not time-based).
    First GET → frame 0, second → frame 1, …, wraps around automatically.
    Returns 256 values, each 8 bits: "0000000{pixel}" (7 padding + 1 color bit).
    """
    global _BADAPPLE_COUNTER
    with _BADAPPLE_COUNTER_LOCK:
        idx = _BADAPPLE_COUNTER % len(_BADAPPLE_FRAMES)
        _BADAPPLE_COUNTER += 1

    bits = _BADAPPLE_FRAMES[idx]
    return JSONResponse(
        [{"value": f"0000000{b}"} for b in bits],
        headers=_NO_STORE,
    )

@app.post("/panel/badapple16/reset", operation_id="panel_badapple16_reset")
def panel_badapple16_reset():
    """Reset the frame counter back to 0 (next GET returns frame 0)."""
    global _BADAPPLE_COUNTER
    with _BADAPPLE_COUNTER_LOCK:
        _BADAPPLE_COUNTER = 0
    return {"status": "reset", "next_frame": 0}
