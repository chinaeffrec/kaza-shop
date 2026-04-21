from pydantic import BaseModel
from typing import Optional

class ProductCreate(BaseModel):
    subcategory_id: int
    name: str
    price: int
    discount_price: Optional[int] = None
    description: Optional[str] = None
    characteristics: Optional[str] = None
    stock: int = 0
    is_active: bool = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    discount_price: Optional[int] = None
    description: Optional[str] = None
    characteristics: Optional[str] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None
    subcategory_id: Optional[int] = None