"""
Бизнес-логика для товаров.
Роуты вызывают сервис, сервис работает с БД и файлами.
"""
import asyncio
import io
import logging
from pathlib import Path
from typing import Optional
import uuid

import aiofiles
from fastapi import BackgroundTasks, HTTPException, UploadFile
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate
from app.models.product import Product
from app.models.subcategory import SubCategory
from app.services.cache_service import invalidate_catalog_cache

MEDIA_DIR = Path("/app/media")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
IMAGE_MAX_DIMENSION = 1000   # px - максимальная сторона после ресайза
IMAGE_QUALITY = 85           # quality при сохранении


def _to_response(p: Product) -> ProductResponse:
    images = [x for x in [
        p.image_file_id,
        getattr(p, "image_file_id_2", None),
        getattr(p, "image_file_id_3", None),
    ] if x]
    return ProductResponse(
        id=p.id,
        subcategory_id=p.subcategory_id,
        name=p.name,
        price=p.price,
        discount_price=p.discount_price,
        description=p.description,
        characteristics=p.characteristics,
        image_file_id=p.image_file_id,
        image_file_id_2=getattr(p, "image_file_id_2", None),
        image_file_id_3=getattr(p, "image_file_id_3", None),
        image_url=f"/media/{p.image_file_id}" if p.image_file_id else None,
        image_url_2=f"/media/{p.image_file_id_2}" if getattr(p, "image_file_id_2", None) else None,
        image_url_3=f"/media/{p.image_file_id_3}" if getattr(p, "image_file_id_3", None) else None,
        images=images,
        has_image=bool(p.image_file_id),
        stock=p.stock or 0,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def get_product_or_404(product_id: int, session: AsyncSession) -> Product:
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")
    return product


async def list_products(
    page: int,
    per_page: int,
    session: AsyncSession,
    search: Optional[str] = None,
    subcategory_id: Optional[int] = None,
    category_id: Optional[int] = None,
    has_image: Optional[bool] = None,
) -> ProductListResponse:
    q = select(Product)

    # Фильтр по категории через JOIN с подкатегориями
    if category_id is not None:
        q = q.join(SubCategory, Product.subcategory_id == SubCategory.id).where(
            SubCategory.category_id == category_id
        )

    if subcategory_id is not None:
        q = q.where(Product.subcategory_id == subcategory_id)

    if search:
        # Приводим к нижнему регистру в Python (корректно для Unicode/кириллицы).
        term = search.strip().lower()
        # Экранируем спецсимволы LIKE, чтобы % и _ из запроса не были wildcards.
        term_safe = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        # lower() — ASCII, translate() — кириллица. Вместе: locale-independent поиск.
        _CYR_UP = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
        _CYR_LO = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        name_norm = func.lower(func.translate(Product.name, _CYR_UP, _CYR_LO))
        q = q.where(name_norm.like(f"%{term_safe}%", escape="\\"))

    if has_image is True:
        q = q.where(Product.image_file_id.isnot(None))
    elif has_image is False:
        q = q.where(Product.image_file_id.is_(None))

    # Общий счётчик - тот же фильтр, без offset/limit
    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * per_page
    result = await session.execute(
        q.order_by(Product.id.asc()).offset(offset).limit(per_page)
    )
    items = [_to_response(p) for p in result.scalars().all()]
    return ProductListResponse(
        items=items, total=total, page=page, per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


async def create_product(data: ProductCreate, session: AsyncSession) -> ProductResponse:
    product = Product(**data.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    await invalidate_catalog_cache()
    return _to_response(product)


async def update_product(product_id: int, data: ProductUpdate, session: AsyncSession) -> ProductResponse:
    product = await get_product_or_404(product_id, session)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    await invalidate_catalog_cache()
    return _to_response(product)


async def delete_product(product_id: int, session: AsyncSession) -> dict:
    product = await get_product_or_404(product_id, session)
    for field in ("image_file_id", "image_file_id_2", "image_file_id_3"):
        fn = getattr(product, field, None)
        if fn:
            p = MEDIA_DIR / fn
            if p.exists():
                p.unlink()
    await session.delete(product)
    await session.commit()
    await invalidate_catalog_cache()
    return {"status": "deleted"}


async def bulk_delete_products(ids: list[int], session: AsyncSession) -> dict:
    ids = sorted(set(i for i in ids if isinstance(i, int) and i > 0))
    if not ids:
        raise HTTPException(400, "No product ids provided")
    result = await session.execute(select(Product).where(Product.id.in_(ids)))
    products = result.scalars().all()
    for product in products:
        for field in ("image_file_id", "image_file_id_2", "image_file_id_3"):
            fn = getattr(product, field, None)
            if fn:
                p = MEDIA_DIR / fn
                if p.exists():
                    p.unlink()
        await session.delete(product)
    await session.commit()
    await invalidate_catalog_cache()
    return {"status": "ok", "deleted": len(products)}


def _photo_field(slot: int) -> str:
    return "image_file_id" if slot == 1 else f"image_file_id_{slot}"


_FORMAT_MAP = {
    "image/jpeg": ("JPEG", "jpg"),
    "image/png":  ("PNG",  "png"),
    "image/webp": ("WEBP", "webp"),
}


def _compress_image(content: bytes, content_type: str) -> tuple[bytes, str]:
    """
    Ресайз до IMAGE_MAX_DIMENSION px по большей стороне.
    Формат сохраняется исходный (JPEG → JPEG, PNG → PNG, WebP → WebP).
    Возвращает (сжатые байты, расширение файла).
    """
    fmt, ext = _FORMAT_MAP.get(content_type, ("JPEG", "jpg"))
    img = Image.open(io.BytesIO(content))

    # PNG / WebP с прозрачностью → белый фон при сохранении в JPEG
    if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = background
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    # Ресайз только если изображение больше лимита
    w, h = img.size
    if max(w, h) > IMAGE_MAX_DIMENSION:
        ratio = IMAGE_MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.BICUBIC)

    buf = io.BytesIO()
    save_kwargs: dict = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = IMAGE_QUALITY
        save_kwargs["optimize"] = True
    elif fmt == "WEBP":
        save_kwargs["quality"] = IMAGE_QUALITY
    img.save(buf, **save_kwargs)
    return buf.getvalue(), ext


_log = logging.getLogger(__name__)


def _compress_and_replace(path: Path, content: bytes, content_type: str) -> None:
    """Синхронная функция — запускается Starlette в thread pool ПОСЛЕ отправки ответа.
    Заменяет сырой файл сжатой версией. Клиент уже получил 200 OK к этому моменту."""
    try:
        compressed, _ = _compress_image(content, content_type)
        path.write_bytes(compressed)
        _log.debug("Background compression done: %s (%d bytes)", path.name, len(compressed))
    except Exception as e:
        _log.warning("Background image compression failed for %s: %s", path.name, e)


async def upload_photo(
    product_id: int, slot: int, file: UploadFile,
    session: AsyncSession, background_tasks: BackgroundTasks,
) -> dict:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(413, f"File too large. Max {MAX_IMAGE_SIZE // 1024 // 1024} MB.")

    # Определяем расширение без запуска Pillow - он уйдёт в фон
    ext = _FORMAT_MAP.get(file.content_type, ("JPEG", "jpg"))[1]

    product = await get_product_or_404(product_id, session)
    field = _photo_field(slot)
    old_fn = getattr(product, field, None)
    if old_fn:
        old_path = MEDIA_DIR / old_fn
        if old_path.exists():
            old_path.unlink()

    suffix = "" if slot == 1 else f"_s{slot}"
    filename = f"product_{product_id}{suffix}_{uuid.uuid4().hex[:8]}.{ext}"
    dest = MEDIA_DIR / filename
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # Сохраняем RAW-файл немедленно - клиент получит ответ без ожидания Pillow
    async with aiofiles.open(dest, "wb") as out:
        await out.write(content)

    setattr(product, field, filename)
    await session.commit()

    # Pillow сжимает в фоне - уже после отправки HTTP-ответа клиенту
    background_tasks.add_task(_compress_and_replace, dest, content, file.content_type)
    await invalidate_catalog_cache()
    return {"status": "ok", "slot": slot, "filename": filename, "url": f"/media/{filename}"}


async def delete_photo(product_id: int, slot: int, session: AsyncSession) -> dict:
    product = await get_product_or_404(product_id, session)
    field = _photo_field(slot)
    fn = getattr(product, field, None)
    if fn:
        path = MEDIA_DIR / fn
        if path.exists():
            path.unlink()
        setattr(product, field, None)
        await session.commit()
        await invalidate_catalog_cache()
    return {"status": "ok"}
