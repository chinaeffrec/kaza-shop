from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.products import Product
from app.api.schemas.product import ProductCreate, ProductOut

router = APIRouter(prefix="/products", tags=["Products"])

@router.post("/", response_model=ProductOut)
async def create_product(
        data: ProductCreate,
        session: AsyncSession = Depends(get_session),
):
    product = Product(**data.dict())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product

@router.get("/", response_model=list[ProductOut])
async def list_products(
        category: str | None = None,
        session: AsyncSession = Depends(get_session)
):
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
        product_id: int,
        session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product

