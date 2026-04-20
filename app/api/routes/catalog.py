from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.category import Category
from app.models.subcategory import SubCategory
from app.models.product import Product

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories")
async def get_categories(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Category))
    categories = result.scalars().all()
    return [{"id": c.id, "name": c.name, "slug": c.slug} for c in categories]


@router.get("/categories/{category_id}/subcategories")
async def get_subcategories(category_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SubCategory).where(SubCategory.category_id == category_id)
    )
    subs = result.scalars().all()
    return [{"id": s.id, "name": s.name, "slug": s.slug} for s in subs]


@router.get("/subcategories/{subcategory_id}/products")
async def get_products(subcategory_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Product).where(Product.subcategory_id == subcategory_id, Product.is_active == True)
    )
    products = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "discount_price": p.discount_price,
            "images": p.images or []
        }
        for p in products
    ]


@router.get("/products/{product_id}")
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.is_active == True)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "discount_price": product.discount_price,
        "description": product.description,
        "characteristics": product.characteristics,
        "images": product.images or [],
        "stock": product.stock,
        "subcategory_id": product.subcategory_id
    }