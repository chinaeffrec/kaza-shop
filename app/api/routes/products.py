import os
import uuid
import aiofiles
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.product import Product
from app.api.schemas.product import ProductCreate, ProductUpdate, ProductOut

router = APIRouter(prefix="/products", tags=["Products"])

MEDIA_DIR = Path(__file__).resolve().parents[3] / "media"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ─────────────────────────────────────────
# POST /products/
# ─────────────────────────────────────────
@router.post("/", response_model=dict)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_session),
):
    product = Product(
        subcategory_id=data.subcategory_id,
        name=data.name,
        price=data.price,
        description=data.description,
        characteristics=data.characteristics,
        is_active=data.is_active,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return _product_dict(product)


# ─────────────────────────────────────────
# GET /products/
# ─────────────────────────────────────────
@router.get("/", response_model=list[dict])
async def list_products(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Product))
    return [_product_dict(p) for p in result.scalars().all()]


# ─────────────────────────────────────────
# GET /products/{id}
# ─────────────────────────────────────────
@router.get("/{product_id}", response_model=dict)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    product = await _get_or_404(product_id, session)
    return _product_dict(product)


# ─────────────────────────────────────────
# PATCH /products/{id}
# ─────────────────────────────────────────
@router.patch("/{product_id}", response_model=dict)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    session: AsyncSession = Depends(get_session),
):
    product = await _get_or_404(product_id, session)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return _product_dict(product)


# ─────────────────────────────────────────
# DELETE /products/{id}
# ─────────────────────────────────────────
@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    product = await _get_or_404(product_id, session)
    await session.delete(product)
    await session.commit()
    return {"status": "deleted"}


# ─────────────────────────────────────────
# POST /products/{id}/photo  — загрузить фото
# ─────────────────────────────────────────
@router.post("/{product_id}/photo")
async def upload_photo(
    product_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG or WebP.",
        )

    product = await _get_or_404(product_id, session)

    # Удаляем старое фото если есть
    if product.image_file_id and not product.image_file_id.startswith("Ag"):
        old_path = MEDIA_DIR / product.image_file_id
        if old_path.exists():
            old_path.unlink()

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"product_{product_id}_{uuid.uuid4().hex[:8]}.{ext}"
    dest = MEDIA_DIR / filename

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(dest, "wb") as out:
        content = await file.read()
        await out.write(content)

    # Храним имя файла; боту передаём URL через /media/
    product.image_file_id = filename
    await session.commit()

    return {"status": "ok", "filename": filename, "url": f"/media/{filename}"}


# ─────────────────────────────────────────
# DELETE /products/{id}/photo
# ─────────────────────────────────────────
@router.delete("/{product_id}/photo")
async def delete_photo(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    product = await _get_or_404(product_id, session)
    if product.image_file_id:
        path = MEDIA_DIR / product.image_file_id
        if path.exists():
            path.unlink()
        product.image_file_id = None
        await session.commit()
    return {"status": "ok"}


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

async def _get_or_404(product_id: int, session: AsyncSession) -> Product:
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _product_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "subcategory_id": p.subcategory_id,
        "name": p.name,
        "price": p.price,
        "description": p.description,
        "characteristics": p.characteristics,
        "image_file_id": p.image_file_id,
        "image_url": f"/media/{p.image_file_id}" if p.image_file_id else None,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
    }
