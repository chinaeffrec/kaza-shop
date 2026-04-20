from pydantic import BaseModel
from typing import Optional


class ProductCreate(BaseModel):
    subcategory_id: int
    name: str
    price: int
    description: Optional[str] = None
    characteristics: Optional[str] = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    characteristics: Optional[str] = None
    is_active: Optional[bool] = None
    subcategory_id: Optional[int] = None


class ProductOut(BaseModel):
    id: int
    subcategory_id: int
    name: str
    price: int
    description: Optional[str]
    characteristics: Optional[str]
    image_file_id: Optional[str]
    image_url: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True
