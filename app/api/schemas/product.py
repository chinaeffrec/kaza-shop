from pydantic import BaseModel
from typing import Optional

class ProductCreate(BaseModel):
    name: str
    category: str
    price: int
    description: Optional[str] = None
    characteristics: Optional[str] = None
    images: Optional[str] = None
    on_sale: Optional[bool] = None

class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    price: int
    description: Optional[str]
    characteristics: Optional[str]
    images: Optional[str]
    on_sale: bool

    class Config:
        from_attributes = True
