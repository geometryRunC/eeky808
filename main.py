from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="My Render API")

# --- Data Model for POST requests ---
class Item(BaseModel):
    name: str
    price: float
    is_offer: Optional[bool] = None

# --- Root Endpoint ---
@app.get("/")
def read_root():
    return {"message": "Hello from Render! Your API is live."}

# --- GET Endpoint with Path & Query Parameters ---
@app.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None):
    return {"item_id": item_id, "q": q}

# --- POST Endpoint (for creating data) ---
@app.post("/items/")
def create_item(item: Item):
    # In a real app, you would save this to a database
    return {"item_name": item.name, "item_price": item.price, "received": True}
