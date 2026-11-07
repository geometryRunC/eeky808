from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="eeky808")

BASE_DIR = Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
# ---------- HOMEPAGE (HTML via Jinja2) ----------
@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    context = {
        "request": request,
        "title": "eeky808",
        "heading": "adsgrup",
        "intro": "my build logic site♥️LMAO",
    }
    return templates.TemplateResponse("index.html", context)

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
