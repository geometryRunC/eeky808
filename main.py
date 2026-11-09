from pathlib import Path
import io
import time
import threading

from fastapi import FastAPI, APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

try:
    from PIL import Image, ImageOps
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from truthtable import TEXT_PANEL_TRUTH, to_8bit

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="eeky808")

static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ---------- PAGES ----------
@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "title": "eeky808",
        "heading": "eeky808",
        "tagline": "my build logic site or whatever",
        "intro": "made this cuz im obsessed with build logic on roblox lol",
    })

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tool", response_class=HTMLResponse)
def tool_page(request: Request):
    return templates.TemplateResponse(request, "tool.html", {"request": request, "title": "text panel tool - eeky808"})

@app.get("/truthtable", response_class=HTMLResponse)
def truthtable_page(request: Request):
    return templates.TemplateResponse(request, "truthtable.html", {"request": request, "title": "truth table - eeky808"})

@app.get("/image", response_class=HTMLResponse)
def image_page(request: Request):
    return templates.TemplateResponse(request, "image.html", {"request": request, "title": "image panel - eeky808"})

@app.get("/test/panel16", response_class=HTMLResponse)
def test_panel16_page(request: Request):
    return templates.TemplateResponse(request, "test_panel16.html", {"request": request, "title": "panel test - 16x16"})

@app.get("/decode", response_class=HTMLResponse)
def decode_page(request: Request):
    return templates.TemplateResponse(request, "decode.html", {
        "request": request,
        "title": "block decoder - eeky808",
    })

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

_SPACE_VALUE = _ALPHABET[" "]["value"]
_NOTHING_VALUE = "10000000"
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
                "shift": s, "i5": a, "i4": b, "i3": c, "i2": d, "i1": e, "i0": f,
                "char": ch, "value": to_8bit(s, a, b, c, d, e, f),
            }
            for s, a, b, c, d, e, f, ch in TEXT_PANEL_TRUTH
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
    ticks = max(1, round(1 / _HELLO_INTERVAL))
    idx = int(time.time() * ticks) % len(_HELLO_WORLD)
    entry = _ALPHABET.get(_HELLO_WORLD[idx])
    return JSONResponse(entry or {"value": _NOTHING_VALUE}, headers=_NO_STORE)

@api.get("/txtpanel/inputs/{char}", operation_id="txtpanel_inputs")
def txtpanel_inputs(char: str):
    if char not in _ALPHABET:
        raise HTTPException(404, f"Character {char!r} not in truth table")
    for s, a, b, c, d, e, f, ch in TEXT_PANEL_TRUTH:
        if ch == char and ch != "":
            return {
                "char": char,
                "value": to_8bit(s, a, b, c, d, e, f),
                "inputs": {"1": a, "2": b, "3": c, "4": d, "5": e, "6": f, "7": s},
            }
    raise HTTPException(404, f"Character {char!r} not found")

@api.get("/txtpanel/nothing", operation_id="txtpanel_nothing")
def txtpanel_nothing():
    return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)

@api.get("/txtpanel/{char}", operation_id="txtpanel_char")
def txtpanel_char(char: str):
    if char in _ALPHABET:
        return {"char": char, **_ALPHABET[char]}
    raise HTTPException(404, f"Character {char!r} not in truth table")

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
    "last_visible_char": None,
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
        vc = _TYPEWRITER_STATE["last_visible_char"]
        vv = _TYPEWRITER_STATE["last_visible_value"]

    now = time.time()
    return JSONResponse({
        "text": text,
        "length": len(text),
        "pos": pos,
        "buffer_length": len(text),
        "panel_active": last_at > 0 and (now - last_at) < 2.0,
        "since_last_served": round(now - last_at, 2) if last_at > 0 else None,
        "panel_char": vc,
        "panel_value": vv,
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

# ---------- Image panel ----------
_IMAGE_LOCK = threading.Lock()
_IMAGE_STATE = {
    "16": {"bits": "", "pos": 0},
    "32": {"bits": "", "pos": {1: 0, 2: 0, 3: 0, 4: 0}},
}

_PANEL_QUADRANTS = {
    1: (range(0, 16),  range(0, 16)),
    2: (range(0, 16),  range(16, 32)),
    3: (range(16, 32), range(0, 16)),
    4: (range(16, 32), range(16, 32)),
}

def _process_image(data: bytes, size: int) -> str:
    if not _PIL_AVAILABLE:
        raise HTTPException(500, "pillow not installed on server")
    try:
        img = Image.open(io.BytesIO(data)).convert("L")
    except Exception as e:
        raise HTTPException(400, f"could not read image: {e}")
    img = ImageOps.fit(img, (size, size), method=Image.Resampling.LANCZOS)
    img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    px = img.load()
    return "".join("1" if px[x, y] > 0 else "0" for y in range(size) for x in range(size))

def _get_quadrant_bits(bits32: str, quadrant: int) -> str:
    rows, cols = _PANEL_QUADRANTS[quadrant]
    return "".join(bits32[y * 32 + x] for y in rows for x in cols)

@api.post("/panel/upload", operation_id="panel_upload")
async def panel_upload(file: UploadFile = File(...)):
    if not _PIL_AVAILABLE:
        raise HTTPException(500, "pillow not installed on server")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "image too big (max 10 MB)")
    bits16 = _process_image(data, 16)
    bits32 = _process_image(data, 32)
    with _IMAGE_LOCK:
        _IMAGE_STATE["16"]["bits"] = bits16
        _IMAGE_STATE["16"]["pos"] = 0
        _IMAGE_STATE["32"]["bits"] = bits32
        _IMAGE_STATE["32"]["pos"] = {1: 0, 2: 0, 3: 0, 4: 0}
    return JSONResponse({"status": "ok", "size16": len(bits16), "size32": len(bits32)}, headers=_NO_STORE)

class DrawBody(BaseModel):
    bits: str

@api.post("/panel/draw", operation_id="panel_draw")
def panel_draw(body: DrawBody):
    bits = (body.bits or "").strip()
    if len(bits) != 256 or any(c not in "01" for c in bits):
        raise HTTPException(400, "bits must be exactly 256 chars of '0' or '1'")
    rows32 = []
    for y in range(16):
        row = bits[y * 16:(y + 1) * 16]
        d = "".join(c * 2 for c in row)
        rows32.append(d)
        rows32.append(d)
    bits32 = "".join(rows32)
    with _IMAGE_LOCK:
        _IMAGE_STATE["16"]["bits"] = bits
        _IMAGE_STATE["16"]["pos"] = 0
        _IMAGE_STATE["32"]["bits"] = bits32
        _IMAGE_STATE["32"]["pos"] = {1: 0, 2: 0, 3: 0, 4: 0}
    return JSONResponse({"status": "ok"}, headers=_NO_STORE)

# ---------- Test smiley ----------
_SMILEY_16 = (
    "0000000000000000"
    "0000000000000000"
    "0000111111110000"
    "0011111111111100"
    "0111111111111110"
    "0111111111111110"
    "1111111111111111"
    "1111001111001111"
    "1111001111001111"
    "1111111111111111"
    "1111111111111111"
    "1111100000011111"
    "0111111111111110"
    "0011111111111100"
    "0000111111110000"
    "0000000000000000"
)

@api.post("/panel/test-smiley", operation_id="panel_test_smiley")
def panel_test_smiley():
    bits = _SMILEY_16
    rows32 = []
    for y in range(16):
        row = bits[y * 16:(y + 1) * 16]
        d = "".join(c * 2 for c in row)
        rows32.append(d)
        rows32.append(d)
    bits32 = "".join(rows32)
    with _IMAGE_LOCK:
        _IMAGE_STATE["16"]["bits"] = bits
        _IMAGE_STATE["16"]["pos"] = 0
        _IMAGE_STATE["32"]["bits"] = bits32
        _IMAGE_STATE["32"]["pos"] = {1: 0, 2: 0, 3: 0, 4: 0}
    return JSONResponse({"status": "ok", "hint": "GET /api/panel/current 256x to stream it"}, headers=_NO_STORE)

@api.get("/panel/test-smiley", operation_id="panel_test_smiley_bits")
def panel_test_smiley_bits():
    return JSONResponse({"bits": _SMILEY_16, "size": 16, "length": 256}, headers=_NO_STORE)

# ---------- Image streaming ----------
@api.get("/panel/current", operation_id="panel_current")
def panel_current():
    with _IMAGE_LOCK:
        bits = _IMAGE_STATE["16"]["bits"]
        if not bits:
            return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)
        pos = _IMAGE_STATE["16"]["pos"]
        if pos >= len(bits):
            return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)
        bit = bits[pos]
        _IMAGE_STATE["16"]["pos"] = pos + 1
    return JSONResponse({"value": f"0000000{bit}"}, headers=_NO_STORE)

@api.get("/panel/panel{quadrant}/current", operation_id="panel_quadrant_current")
def panel_quadrant_current(quadrant: int):
    if quadrant not in _PANEL_QUADRANTS:
        raise HTTPException(404, "no such panel (must be 1-4)")
    with _IMAGE_LOCK:
        bits32 = _IMAGE_STATE["32"]["bits"]
        if not bits32:
            return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)
        qbits = _get_quadrant_bits(bits32, quadrant)
        pos = _IMAGE_STATE["32"]["pos"][quadrant]
        if pos >= len(qbits):
            return JSONResponse({"value": _NOTHING_VALUE}, headers=_NO_STORE)
        bit = qbits[pos]
        _IMAGE_STATE["32"]["pos"][quadrant] = pos + 1
    return JSONResponse({"value": f"0000000{bit}"}, headers=_NO_STORE)

@api.get("/panel/status", operation_id="panel_status")
def panel_status():
    with _IMAGE_LOCK:
        return JSONResponse({
            "16": {"bits": _IMAGE_STATE["16"]["bits"], "length": len(_IMAGE_STATE["16"]["bits"]), "pos": _IMAGE_STATE["16"]["pos"]},
            "32": {"bits": _IMAGE_STATE["32"]["bits"], "length": len(_IMAGE_STATE["32"]["bits"]), "pos": dict(_IMAGE_STATE["32"]["pos"])},
        }, headers=_NO_STORE)

@api.post("/panel/replay", operation_id="panel_replay")
def panel_replay():
    with _IMAGE_LOCK:
        _IMAGE_STATE["16"]["pos"] = 0
        _IMAGE_STATE["32"]["pos"] = {1: 0, 2: 0, 3: 0, 4: 0}
    return JSONResponse({"status": "replay"}, headers=_NO_STORE)

@api.post("/panel/clear", operation_id="panel_clear")
def panel_clear():
    with _IMAGE_LOCK:
        _IMAGE_STATE["16"]["bits"] = ""
        _IMAGE_STATE["16"]["pos"] = 0
        _IMAGE_STATE["32"]["bits"] = ""
        _IMAGE_STATE["32"]["pos"] = {1: 0, 2: 0, 3: 0, 4: 0}
    return JSONResponse({"status": "cleared"}, headers=_NO_STORE)

# ---------- Block decoder (Build Logic) ----------
_BASE71 = list("0123456789abcdefghijklmnopqrstuvwxyz"
               "ABCDEFGHIJKLMNOPQRSTUVWXYZ!@$%?&<()")

_VALID_BLOCK_TYPES = {"speaker", "keypad", "legacykeypad"}

def _decode_base71(value: str) -> int:
    """Decode a base-71 string into an integer (matches the JS decoder)."""
    out = 0
    for i, ch in enumerate(reversed(value)):
        out += _BASE71.index(ch) * (71 ** i)
    return out

def _decode_chunks(value: str) -> list[str]:
    """Split an encoded block value into length-prefixed chunks."""
    chunks = []
    idx = 0
    while idx < len(value):
        length_char = value[idx]
        length = _BASE71.index(length_char) + 1
        idx += 1
        chunks.append(value[idx:idx + length])
        idx += length
    return chunks

def _decode_block(block_type: str, value: str) -> dict:
    """Decode a block value into its fields. Mirrors the JS decoder exactly."""
    decoded = _decode_chunks(value)
    if len(decoded) < 2:
        raise ValueError(f"expected at least 2 chunks, got {len(decoded)}")

    result = {"your input": value}

    if block_type == "speaker":
        result["looped"] = "ON" if decoded[0] == "1" else "OFF"
        result["sound id"] = _decode_base71(decoded[1])
        result["volume"] = decoded[2]
        result["pitch"] = decoded[3]

    elif block_type == "keypad":
        result["unlock on enter"] = "ON" if decoded[0] == "1" else "OFF"
        result["unlocked time"] = decoded[1]
        code_digits = decoded[2] if len(decoded) > 2 else ""
        joined = ""
        for part in code_digits.split(":"):
            s = str(_decode_base71(part))
            joined += s[1:]   # drop first char, matches JS substring(1)
        result["code digits"] = joined
        result["show key press"] = "ON" if decoded[3] == "1" else "OFF"
        result["button hold time"] = decoded[4]

    elif block_type == "legacykeypad":
        result["unlock on enter"] = "ON" if decoded[0] == "1" else "OFF"
        result["unlocked time"] = decoded[1]
        result["code digits"] = decoded[2]
        result["show key press"] = "ON" if decoded[3] == "1" else "OFF"
        result["button hold time"] = decoded[4]

    return result

class DecodeBody(BaseModel):
    type: str
    value: str

@api.post("/decode", operation_id="decode_block")
def decode_block(body: DecodeBody):
    """Decode a Build Logic block value. Returns the parsed fields."""
    if body.type not in _VALID_BLOCK_TYPES:
        raise HTTPException(
            400,
            f"invalid block type {body.type!r} — must be one of {sorted(_VALID_BLOCK_TYPES)}",
        )
    try:
        result = _decode_block(body.type, body.value)
    except ValueError as e:
        raise HTTPException(400, f"could not decode: {e}")
    except Exception as e:
        raise HTTPException(400, f"decode error: {e}")

    return JSONResponse(result, headers=_NO_STORE)

# ---------- Mount router ----------
app.include_router(api)
