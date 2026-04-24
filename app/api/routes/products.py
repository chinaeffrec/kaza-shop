import uuid
import aiofiles
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_session
from app.models.product import Product
from app.api.schemas.product import ProductCreate, ProductUpdate

router = APIRouter(prefix="/products", tags=["Products"])

# MEDIA_DIR должен совпадать с тем куда монтируется volume в docker-compose
# ./app/media:/app/app/media  →  файлы лежат в /app/app/media
# main.py раздаёт StaticFiles из BASE_DIR/"media" = /app/app/media
MEDIA_DIR = Path(__file__).resolve().parents[2] / "media"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

async def _reload_bot_cache():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2) as client:
            await client.post("http://bot:8001/reload-cache")
    except Exception:
        pass

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





@router.post("/", response_model=dict)
async def create_product(data: ProductCreate, session: AsyncSession = Depends(get_session)):
    product = Product(**data.dict())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    await _reload_bot_cache()
    return _product_dict(product)



@router.get("/", response_model=list[dict])
async def list_products(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Product))
    return [_product_dict(p) for p in result.scalars().all()]


@router.get("/{product_id}", response_model=dict)
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    return _product_dict(await _get_or_404(product_id, session))


@router.patch("/{product_id}", response_model=dict)
async def update_product(product_id: int, data: ProductUpdate, session: AsyncSession = Depends(get_session)):
    product = await _get_or_404(product_id, session)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    await _reload_bot_cache()
    return _product_dict(product)


@router.delete("/{product_id}")
async def delete_product(product_id: int, session: AsyncSession = Depends(get_session)):
    product = await _get_or_404(product_id, session)
    await session.delete(product)
    await session.commit()
    await _reload_bot_cache()
    return {"status": "deleted"}


@router.post("/{product_id}/photo")
async def upload_photo(product_id: int, file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")
    product = await _get_or_404(product_id, session)

    if product.image_file_id:
        old = MEDIA_DIR / product.image_file_id
        if old.exists():
            old.unlink()

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"product_{product_id}_{uuid.uuid4().hex[:8]}.{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    async with aiofiles.open(MEDIA_DIR / filename, "wb") as out:
        await out.write(content)

    product.image_file_id = filename
    await session.commit()
    return {"status": "ok", "filename": filename, "url": f"/media/{filename}"}


@router.delete("/{product_id}/photo")
async def delete_photo(product_id: int, session: AsyncSession = Depends(get_session)):
    product = await _get_or_404(product_id, session)
    if product.image_file_id:
        path = MEDIA_DIR / product.image_file_id
        if path.exists():
            path.unlink()
        product.image_file_id = None
        await session.commit()
    return {"status": "ok"}


async def _get_or_404(product_id: int, session: AsyncSession) -> Product:
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")
    return product


def _product_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "subcategory_id": p.subcategory_id,
        "name": p.name,
        "price": p.price,
        "discount_price": p.discount_price,
        "description": p.description,
        "characteristics": p.characteristics,
        "image_file_id": p.image_file_id,
        "image_url": f"/media/{p.image_file_id}" if p.image_file_id else None,
        "has_image": bool(p.image_file_id),
        "stock": p.stock,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
