from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import insert
from app.db.session import get_session
from app.models.cart import Cart
from app.models.products import Product



router = APIRouter(prefix="/cart", tags=["cart"])
@router.post("/", response_model=None)
async def add_to_cart(
    data: dict,
    session: AsyncSession = Depends(get_session)
):
    user_id = data["user_id"]
    product_id = data["product_id"]
    quantity = data.get("quantity", 1)
    result = await session.execute(
        select(Cart).where(
            Cart.user_id == user_id,
            Cart.product_id == product_id
        )
    )
    cart_item = result.scalar_one_or_none()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity
        )
        session.add(cart_item)
    await session.commit()
    return {"status": "ok"}

@router.get("/{user_id}")
async def get_cart(
    user_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Cart, Product)
        .join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id)
    )

    rows = result.all()
    items = []
    total = 0

    for cart, product in rows:
        items_total = product.price * cart.quantity
        total += items_total

        items.append({
            "name": product.name,
            "price": product.price,
            "quantity": cart.quantity,
            "sum": items_total
        })

        return {
            "items": items,
            "total": total
        }