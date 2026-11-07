from pathlib import Path
import itertools, threading

from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="eeky808")

static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
# ---------- Static files & templates ----------
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")# ---------- HOMEPAGE (HTML via Jinja2) ----------
@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    context = {
        "request": request,
        "title": "eeky808",
        "heading": "adsgrup",
        "intro": "my build logic site♥️LMAO",
    }
    return templates.TemplateResponse(request, "index.html", context)

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

app.include_router(api)

@app.get("/debug/files")
def debug_files():
    import os
    src = "/opt/render/project/src"
    result = {"cwd": os.getcwd(), "root": sorted(os.listdir(src))}
    tpl = os.path.join(src, "templates")
    if os.path.isdir(tpl):
        result["templates"] = sorted(os.listdir(tpl))
    else:
        result["templates"] = "MISSING"
    return result

# ---------- Text Panel Truth Table (7 inputs → 8-bit output) ----------
# Format: (shift, i5, i4, i3, i2, i1, i0, char)
_TEXT_PANEL_TRUTH = [
    (0, 0, 0, 0, 0, 0, 0, ""),  # empty, skipped
    (0, 0, 0, 0, 0, 0, 1, "a"),
    (0, 0, 0, 0, 0, 1, 0, "b"),
    (0, 0, 0, 0, 0, 1, 1, "c"),
    (0, 0, 0, 0, 1, 0, 0, "d"),
    (0, 0, 0, 0, 1, 0, 1, "e"),
    (0, 0, 0, 0, 1, 1, 0, "f"),
    (0, 0, 0, 0, 1, 1, 1, "g"),
    (0, 0, 0, 1, 0, 0, 0, "h"),
    (0, 0, 0, 1, 0, 0, 1, "i"),
    (0, 0, 0, 1, 0, 1, 0, "j"),
    (0, 0, 0, 1, 0, 1, 1, "k"),
    (0, 0, 0, 1, 1, 0, 0, "l"),
    (0, 0, 0, 1, 1, 0, 1, "m"),
    (0, 0, 0, 1, 1, 1, 0, "n"),
    (0, 0, 0, 1, 1, 1, 1, "o"),
    (0, 0, 1, 0, 0, 0, 0, "p"),
    (0, 0, 1, 0, 0, 0, 1, "q"),
    (0, 0, 1, 0, 0, 1, 0, "r"),
    (0, 0, 1, 0, 0, 1, 1, "s"),
    (0, 0, 1, 0, 1, 0, 0, "t"),
    (0, 0, 1, 0, 1, 0, 1, "u"),
    (0, 0, 1, 0, 1, 1, 0, "v"),
    (0, 0, 1, 0, 1, 1, 1, "w"),
    (0, 0, 1, 1, 0, 0, 0, "x"),
    (0, 0, 1, 1, 0, 0, 1, "y"),
    (0, 0, 1, 1, 0, 1, 0, "z"),
    (0, 0, 1, 1, 0, 1, 1, "1"),
    (0, 0, 1, 1, 1, 0, 0, "2"),
    (0, 0, 1, 1, 1, 0, 1, "3"),
    (0, 0, 1, 1, 1, 1, 0, "4"),
    (0, 0, 1, 1, 1, 1, 1, "5"),
    (0, 1, 0, 0, 0, 0, 0, "6"),
    (0, 1, 0, 0, 0, 0, 1, "7"),
    (0, 1, 0, 0, 0, 1, 0, "8"),
    (0, 1, 0, 0, 0, 1, 1, "9"),
    (0, 1, 0, 0, 1, 0, 0, "0"),
    (0, 1, 0, 0, 1, 0, 1, "-"),
    (0, 1, 0, 0, 1, 1, 0, "="),
    (0, 1, 0, 0, 1, 1, 1, "."),
    (0, 1, 0, 1, 0, 0, 0, ","),
    (0, 1, 0, 1, 0, 0, 1, ";"),
    (0, 1, 0, 1, 0, 1, 0, "/"),
    (0, 1, 0, 1, 0, 1, 1, "à"),
    (0, 1, 0, 1, 1, 0, 0, "â"),
    (0, 1, 0, 1, 1, 0, 1, "ç"),
    (0, 1, 0, 1, 1, 1, 0, "è"),
    (0, 1, 0, 1, 1, 1, 1, "é"),
    (0, 1, 1, 0, 0, 0, 0, "ê"),
    (0, 1, 1, 0, 0, 0, 1, "î"),
    (0, 1, 1, 0, 0, 1, 0, "ï"),
    (0, 1, 1, 0, 0, 1, 1, "û"),
    (0, 1, 1, 0, 1, 0, 0, ""),  # empty, skipped
    (0, 1, 1, 0, 1, 0, 1, "["),
    (0, 1, 1, 0, 1, 1, 0, "]"),
    (0, 1, 1, 0, 1, 1, 1, '"'),
    (0, 1, 1, 1, 0, 0, 0, "🟧"),
    (0, 1, 1, 1, 0, 0, 1, "🟨"),
    (0, 1, 1, 1, 0, 1, 0, "🟩"),
    (0, 1, 1, 1, 0, 1, 1, "🟦"),
    (0, 1, 1, 1, 1, 0, 0, "🟪"),
    (0, 1, 1, 1, 1, 0, 1, "⬜"),
    (0, 1, 1, 1, 1, 1, 0, "▶"),
    (0, 1, 1, 1, 1, 1, 1, " "),
    (1, 0, 0, 0, 0, 0, 0, " "),  # duplicate space, skipped
    (1, 0, 0, 0, 0, 0, 1, "A"),
    (1, 0, 0, 0, 0, 1, 0, "B"),
    (1, 0, 0, 0, 0, 1, 1, "C"),
    (1, 0, 0, 0, 1, 0, 0, "D"),
    (1, 0, 0, 0, 1, 0, 1, "E"),
    (1, 0, 0, 0, 1, 1, 0, "F"),
    (1, 0, 0, 0, 1, 1, 1, "G"),
    (1, 0, 0, 1, 0, 0, 0, "H"),
    (1, 0, 0, 1, 0, 0, 1, "I"),
    (1, 0, 0, 1, 0, 1, 0, "J"),
    (1, 0, 0, 1, 0, 1, 1, "K"),
    (1, 0, 0, 1, 1, 0, 0, "L"),
    (1, 0, 0, 1, 1, 0, 1, "M"),
    (1, 0, 0, 1, 1, 1, 0, "N"),
    (1, 0, 0, 1, 1, 1, 1, "O"),
    (1, 0, 1, 0, 0, 0, 0, "P"),
    (1, 0, 1, 0, 0, 0, 1, "Q"),
    (1, 0, 1, 0, 0, 1, 0, "R"),
    (1, 0, 1, 0, 0, 1, 1, "S"),
    (1, 0, 1, 0, 1, 0, 0, "T"),
    (1, 0, 1, 0, 1, 0, 1, "U"),
    (1, 0, 1, 0, 1, 1, 0, "V"),
    (1, 0, 1, 0, 1, 1, 1, "W"),
    (1, 0, 1, 1, 0, 0, 0, "X"),
    (1, 0, 1, 1, 0, 0, 1, "Y"),
    (1, 0, 1, 1, 0, 1, 0, "Z"),
    (1, 0, 1, 1, 0, 1, 1, "!"),
    (1, 0, 1, 1, 1, 0, 0, "@"),
    (1, 0, 1, 1, 1, 0, 1, "#"),
    (1, 0, 1, 1, 1, 1, 0, "$"),
    (1, 0, 1, 1, 1, 1, 1, "%"),
    (1, 1, 0, 0, 0, 0, 0, "?"),
    (1, 1, 0, 0, 0, 0, 1, "&"),
    (1, 1, 0, 0, 0, 1, 0, "*"),
    (1, 1, 0, 0, 0, 1, 1, "("),
    (1, 1, 0, 0, 1, 0, 0, ")"),
    (1, 1, 0, 0, 1, 0, 1, "_"),
    (1, 1, 0, 0, 1, 1, 0, "+"),
    (1, 1, 0, 0, 1, 1, 1, "."),  # duplicate period, skipped
    (1, 1, 0, 1, 0, 0, 0, "'"),
    (1, 1, 0, 1, 0, 0, 1, ":"),
    (1, 1, 0, 1, 0, 1, 0, "~"),
    (1, 1, 0, 1, 0, 1, 1, "À"),
    (1, 1, 0, 1, 1, 0, 0, "Â"),
    (1, 1, 0, 1, 1, 0, 1, "Ç"),
    (1, 1, 0, 1, 1, 1, 0, "È"),
    (1, 1, 0, 1, 1, 1, 1, "É"),
    (1, 1, 1, 0, 0, 0, 0, "Ê"),
    (1, 1, 1, 0, 0, 0, 1, "Ì"),
    (1, 1, 1, 0, 0, 1, 0, "Ï"),
    (1, 1, 1, 0, 0, 1, 1, "Û"),
    (1, 1, 1, 0, 1, 0, 0, "¦"),
    (1, 1, 1, 0, 1, 0, 1, "{"),
    (1, 1, 1, 0, 1, 1, 0, "}"),
    (1, 1, 1, 0, 1, 1, 1, "^"),
    (1, 1, 1, 1, 0, 0, 0, ">"),
    (1, 1, 1, 1, 0, 0, 1, "<"),
    (1, 1, 1, 1, 0, 1, 0, "█"),
    (1, 1, 1, 1, 0, 1, 1, "➡"),
    (1, 1, 1, 1, 1, 0, 0, "⬅"),
    (1, 1, 1, 1, 1, 0, 1, "⬆"),
    (1, 1, 1, 1, 1, 1, 0, "⬇"),
    (1, 1, 1, 1, 1, 1, 1, " "),  # duplicate space, skipped
]

def _to_8bit(shift, i5, i4, i3, i2, i1, i0) -> str:
    """7 input bits → 8-bit binary string (leading 0 prepended)."""
    return f"0{shift}{i5}{i4}{i3}{i2}{i1}{i0}"

# Build the lookup map once at import time
_ALPHABET: dict = {}
for _shift, _i5, _i4, _i3, _i2, _i1, _i0, _char in _TEXT_PANEL_TRUTH:
    if _char == "":
        continue  # skip empty entries
    if _char in _ALPHABET:
        continue  # first occurrence wins (handles duplicate space / period)
    _ALPHABET[_char] = {"value": _to_8bit(_shift, _i5, _i4, _i3, _i2, _i1, _i0)}

@api.get("/alphabet/table")
def alphabet_table(response: Response):
    """Full truth table as an ordered list of {value: "8-bit"} entries."""
    response.headers["Cache-Control"] = "no-store"
    return [
        {"value": obj["value"]}
        for obj in _ALPHABET.values()
    ]

_counter = itertools.count()
_lock = threading.Lock()
_state = {"idx": 0}

@api.get("/alphabet/current")
def alphabet_current(response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not _ALPHABET:
        return {"value": "00000000"}
    chars = list(_ALPHABET.keys())
    with _lock:
        idx = _state["idx"]
        _state["idx"] = (idx + 1) % len(chars)
    return _ALPHABET[chars[idx]]

@api.get("/alphabet/{char}")
def get_char_value(char: str):
    """Look up a single character's 8-bit value."""
    if char in _ALPHABET:
        return {"char": char, **_ALPHABET[char]}
    raise HTTPException(status_code=404, detail=f"Character {char!r} not in truth table")
