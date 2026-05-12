"""Роуты каталога - публичные (для бота) + защищённый reload."""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import require_auth
from app.api.schemas.catalog import (
    CacheReloadResponse, CatalogProductResponse,
    CategoryResponse, SubCategoryResponse,
)
from app.db.session import get_session
from app.models.category import Category
from app.models.product import Product
from app.models.subcategory import SubCategory
from app.services.cache_service import invalidate_catalog_cache
from app.services.settings_service import get_shop_settings

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Category))
    return [CategoryResponse(id=c.id, name=c.name) for c in result.scalars().all()]


@router.get("/subcategories", response_model=List[SubCategoryResponse])
async def get_all_subcategories(session: AsyncSession = Depends(get_session)):
    """Все подкатегории одним запросом — для панели управления."""
    result = await session.execute(select(SubCategory).order_by(SubCategory.category_id, SubCategory.id))
    return [SubCategoryResponse(id=s.id, name=s.name, category_id=s.category_id) for s in result.scalars().all()]


@router.get("/categories/{category_id}/subcategories", response_model=List[SubCategoryResponse])
async def get_subcategories(category_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SubCategory).where(SubCategory.category_id == category_id)
    )
    return [SubCategoryResponse(id=s.id, name=s.name, category_id=s.category_id) for s in result.scalars().all()]


@router.get("/subcategories/{subcategory_id}/products", response_model=List[CatalogProductResponse])
async def get_products(subcategory_id: int, session: AsyncSession = Depends(get_session)):
    shop = await get_shop_settings(session)
    hide_oos = shop.hide_out_of_stock or False

    q = select(Product).where(
        Product.subcategory_id == subcategory_id,
        Product.is_active == True,
    ).order_by(func.lower(Product.name).asc(), Product.id.asc())
    if hide_oos:
        q = q.where(Product.stock > 0)

    products = (await session.execute(q)).scalars().all()
    return [
        CatalogProductResponse(
            id=p.id, name=p.name, price=p.price, discount_price=p.discount_price,
            description=p.description, characteristics=p.characteristics,
            image_file_id=p.image_file_id,
            image_url=f"/media/{p.image_file_id}" if p.image_file_id else None,
            image_url_2=f"/media/{p.image_file_id_2}" if getattr(p, "image_file_id_2", None) else None,
            image_url_3=f"/media/{p.image_file_id_3}" if getattr(p, "image_file_id_3", None) else None,
            stock=p.stock or 0,
            images=[x for x in [
                p.image_file_id,
                getattr(p, "image_file_id_2", None),
                getattr(p, "image_file_id_3", None),
            ] if x],
        )
        for p in products
    ]


@router.get("/products/{product_id}", response_model=CatalogProductResponse)
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    from fastapi import HTTPException
    result = await session.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")
    return CatalogProductResponse(
        id=p.id, name=p.name, price=p.price, discount_price=p.discount_price,
        description=p.description, characteristics=p.characteristics,
        image_file_id=p.image_file_id,
        image_url=f"/media/{p.image_file_id}" if p.image_file_id else None,
        image_url_2=None, image_url_3=None, stock=p.stock or 0, images=[],
    )


@router.post("/cache/reload", response_model=CacheReloadResponse)
async def reload_cache(_: str = Depends(require_auth)):
    await invalidate_catalog_cache()
    return CacheReloadResponse(status="ok", message="Кэш каталога перезагружен")
