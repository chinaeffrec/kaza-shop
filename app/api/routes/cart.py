from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from app.db.session import get_session
from app.models.cart import Cart
from app.models.product import Product

router = APIRouter(prefix="/cart", tags=["cart"])


@router.post("/")
async def add_to_cart(data: dict, session: AsyncSession = Depends(get_session)):
    user_id = data["user_id"]
    product_id = data["product_id"]
    quantity = data.get("quantity", 1)

    # Проверяем существование товара
    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Проверяем наличие в корзине
    result = await session.execute(
        select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    )
    cart_item = result.scalar_one_or_none()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(user_id=user_id, product_id=product_id, quantity=quantity)
        session.add(cart_item)

    await session.commit()
    return {"status": "ok", "message": "Товар добавлен в корзину"}


@router.get("/{user_id}")
async def get_cart(user_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Cart, Product)
        .join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id)
    )
    rows = result.all()

    items = []
    total = 0

    for cart, product in rows:
        item_total = product.price * cart.quantity
        total += item_total
        items.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": cart.quantity,
            "sum": item_total
        })

    return {"items": items, "total": total}


@router.post("/inc")
async def inc_item(data: dict, session: AsyncSession = Depends(get_session)):
    user_id = data["user_id"]
    product_id = data["product_id"]

    await session.execute(
        update(Cart)
        .where(Cart.user_id == user_id, Cart.product_id == product_id)
        .values(quantity=Cart.quantity + 1)
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/dec")
async def dec_item(data: dict, session: AsyncSession = Depends(get_session)):
    user_id = data["user_id"]
    product_id = data["product_id"]

    result = await session.execute(
        select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    )
    item = result.scalar_one_or_none()

    if item:
        if item.quantity > 1:
            item.quantity -= 1
        else:
            await session.delete(item)
        await session.commit()

    return {"status": "ok"}


@router.post("/remove")
async def remove_item(data: dict, session: AsyncSession = Depends(get_session)):
    user_id = data["user_id"]
    product_id = data["product_id"]

    await session.execute(
        delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    )
    await session.commit()
    return {"status": "ok"}