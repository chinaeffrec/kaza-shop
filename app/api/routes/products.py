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

router = APIRouter(prefix="/products", tags=["Products"])

MEDIA_DIR = Path("/app/media")
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
    # Сортируем по id — порядок не меняется после редактирования
    result = await session.execute(select(Product).order_by(Product.id.asc()))
    return [_product_dict(p) for p in result.scalars().all()]


# @router.get("/{product_id}", response_model=dict)
# async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
#     return _product_dict(await _get_or_404(product_id, session))


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
    # Удаляем все фото
    for field in ("image_file_id", "image_file_id_2", "image_file_id_3"):
        fn = getattr(product, field, None)
        if fn:
            p = MEDIA_DIR / fn
            if p.exists():
                p.unlink()
    await session.delete(product)
    await session.commit()
    await _reload_bot_cache()
    return {"status": "deleted"}


# ─── Фото (слот 1 — основное, слоты 2 и 3 — дополнительные) ─────────────────

def _photo_field(slot: int) -> str:
    """Возвращает имя поля модели для данного слота фото."""
    if slot == 1:
        return "image_file_id"
    return f"image_file_id_{slot}"


# @router.post("/{product_id}/photo")
# async def upload_photo(
#     product_id: int,
#     file: UploadFile = File(...),
#     session: AsyncSession = Depends(get_session),
# ):
#     """Загрузка основного фото (слот 1)."""
#     return await _upload_slot(product_id, 1, file, session)


# @router.delete("/{product_id}/photo")
# async def delete_photo(product_id: int, session: AsyncSession = Depends(get_session)):
#     """Удаление основного фото (слот 1)."""
#     return await _delete_slot(product_id, 1, session)


@router.post("/{product_id}/photo/{slot}")
async def upload_photo_slot(
    product_id: int,
    slot: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Загрузка фото в слот 1, 2 или 3."""
    if slot not in (1, 2, 3):
        raise HTTPException(400, "Slot must be 1, 2 or 3")
    return await _upload_slot(product_id, slot, file, session)


@router.delete("/{product_id}/photo/{slot}")
async def delete_photo_slot(
    product_id: int,
    slot: int,
    session: AsyncSession = Depends(get_session),
):
    """Удаление фото из слота 1, 2 или 3."""
    if slot not in (1, 2, 3):
        raise HTTPException(400, "Slot must be 1, 2 or 3")
    return await _delete_slot(product_id, slot, session)


async def _upload_slot(product_id: int, slot: int, file: UploadFile, session: AsyncSession):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported type: {file.content_type}. Use JPEG, PNG or WebP.")
    product = await _get_or_404(product_id, session)
    field = _photo_field(slot)

    # Удаляем старый файл если есть
    old_fn = getattr(product, field, None)
    if old_fn:
        old_path = MEDIA_DIR / old_fn
        if old_path.exists():
            old_path.unlink()

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    suffix = "" if slot == 1 else f"_s{slot}"
    filename = f"product_{product_id}{suffix}_{uuid.uuid4().hex[:8]}.{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    async with aiofiles.open(MEDIA_DIR / filename, "wb") as out:
        await out.write(content)

    setattr(product, field, filename)
    await session.commit()
    await _reload_bot_cache()
    return {"status": "ok", "slot": slot, "filename": filename, "url": f"/media/{filename}"}


async def _delete_slot(product_id: int, slot: int, session: AsyncSession):
    product = await _get_or_404(product_id, session)
    field = _photo_field(slot)
    fn = getattr(product, field, None)
    if fn:
        path = MEDIA_DIR / fn
        if path.exists():
            path.unlink()
        setattr(product, field, None)
        await session.commit()
        await _reload_bot_cache()
    return {"status": "ok"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _get_or_404(product_id: int, session: AsyncSession) -> Product:
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")
    return product


def _product_dict(p: Product) -> dict:
    # Собираем список всех фото (только непустые)
    images = [
        f for f in [
            p.image_file_id,
            getattr(p, "image_file_id_2", None),
            getattr(p, "image_file_id_3", None),
        ] if f
    ]
    return {
        "id": p.id,
        "subcategory_id": p.subcategory_id,
        "name": p.name,
        "price": p.price,
        "discount_price": p.discount_price,
        "description": p.description,
        "characteristics": p.characteristics,
        "image_file_id": p.image_file_id,
        "image_file_id_2": getattr(p, "image_file_id_2", None),
        "image_file_id_3": getattr(p, "image_file_id_3", None),
        "image_url": f"/media/{p.image_file_id}" if p.image_file_id else None,
        "image_url_2": f"/media/{p.image_file_id_2}" if getattr(p, "image_file_id_2", None) else None,
        "image_url_3": f"/media/{p.image_file_id_3}" if getattr(p, "image_file_id_3", None) else None,
        "images": images,
        "has_image": bool(p.image_file_id),
        "stock": p.stock,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }