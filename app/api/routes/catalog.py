from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.category import Category
from app.models.product import Product
from app.models.subcategory import SubCategory

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories")
async def get_categories(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Category))
    return [{"id": c.id, "name": c.name} for c in result.scalars().all()]


@router.get("/categories/{category_id}/subcategories")
async def get_subcategories(category_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SubCategory).where(SubCategory.category_id == category_id)
    )
    return [{"id": s.id, "name": s.name} for s in result.scalars().all()]


@router.get("/subcategories/{subcategory_id}/products")
async def get_products(
    subcategory_id: int,
    session: AsyncSession = Depends(get_session)
):
    hide_oos = False
    try:
        from app.models.settings import ShopSettings
        cfg_res = await session.execute(
            select(ShopSettings).where(ShopSettings.id == 1)
        )
        cfg = cfg_res.scalar_one_or_none()
        if cfg:
            hide_oos = cfg.hide_out_of_stock or False
    except Exception:
        pass

    query = select(Product).where(
        Product.subcategory_id == subcategory_id,
        Product.is_active == True
    ).order_by(func.lower(Product.name).asc(), Product.id.asc())
    if hide_oos:
        query = query.where(Product.stock > 0)

    result = await session.execute(query)
    products = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "discount_price": p.discount_price,
            "description": p.description,
            "characteristics": p.characteristics,
            "image_file_id": p.image_file_id,
            "image_url": f"/media/{p.image_file_id}" if p.image_file_id else None,
            "image_url_2": f"/media/{getattr(p, 'image_file_id_2', None)}" if getattr(p, "image_file_id_2",
                                                                                      None) else None,
            "image_url_3": f"/media/{getattr(p, 'image_file_id_3', None)}" if getattr(p, "image_file_id_3",
                                                                                      None) else None,
            "stock": p.stock,
            "images": [
                x for x in [
                    p.image_file_id,
                    getattr(p, "image_file_id_2", None),
                    getattr(p, "image_file_id_3", None),
                ] if x
            ],
        }
        for p in products
    ]


@router.get("/products/{product_id}")
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return {"error": "not found"}
    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "discount_price": product.discount_price,
        "description": product.description,
        "characteristics": product.characteristics,
        "image_file_id": product.image_file_id,
        "image_url": f"/media/{product.image_file_id}" if product.image_file_id else None,
        "subcategory_id": product.subcategory_id,
        "stock": product.stock,
    }


@router.post("/cache/reload")
async def reload_cache():
# Сбрасывает кэш каталога в боте
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post("http://bot:8001/reload-cache")
        return {"status": "ok", "message": "Кэш каталога перезагружен"}
    except Exception as e:
        return {"status": "partial", "message": f"Бот перезагружает кэш: {e}"}
