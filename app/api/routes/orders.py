from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.models.order import Order, OrderItem, ORDER_STATUSES
from app.models.cart import Cart
from app.models.product import Product
from app.models.product_stats import ProductStats

router = APIRouter(prefix="/orders", tags=["orders"])


async def _inc_ordered(product_id: int, qty: int, session: AsyncSession):
    res = await session.execute(
        select(ProductStats).where(ProductStats.product_id == product_id)
    )
    s = res.scalar_one_or_none()
    if not s:
        s = ProductStats(product_id=product_id)
        session.add(s)
    s.ordered += qty


@router.post("/")
async def create_order(data: dict, session: AsyncSession = Depends(get_session)):
    user_id = data["user_id"]
    result = await session.execute(
        select(Cart, Product).join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total = sum(p.price * c.quantity for c, p in rows)
    order = Order(user_id=user_id, total=total, status="new")
    session.add(order)
    await session.flush()

    for cart, product in rows:
        session.add(OrderItem(
            order_id=order.id, product_id=product.id,
            name=product.name, price=product.price, quantity=cart.quantity,
        ))
        await _inc_ordered(product.id, cart.quantity, session)
        await session.delete(cart)

    await session.commit()
    await session.refresh(order)
    return {
        "id": order.id, "user_id": order.user_id,
        "total": order.total, "status": order.status,
        "created_at": order.created_at.isoformat(),
    }


@router.get("/user/{user_id}")
async def get_user_orders(user_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    return [_order_dict(o) for o in result.scalars().all()]


@router.get("/")
async def list_orders(status: str | None = None, session: AsyncSession = Depends(get_session)):
    query = select(Order).order_by(Order.created_at.desc())
    if status:
        query = query.where(Order.status == status)
    result = await session.execute(query)
    return [_order_dict(o) for o in result.scalars().all()]


@router.get("/statuses")
async def get_statuses():
    return [{"value": k, "label": v} for k, v in ORDER_STATUSES.items()]


@router.get("/{order_id}")
async def get_order(order_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items_result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    items = items_result.scalars().all()
    return {
        **_order_dict(order),
        "items": [{"product_id": i.product_id, "name": i.name,
                   "price": i.price, "quantity": i.quantity, "sum": i.price * i.quantity}
                  for i in items],
    }


@router.patch("/{order_id}/status")
async def update_order_status(order_id: int, data: dict, session: AsyncSession = Depends(get_session)):
    new_status = data.get("status")
    if new_status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = new_status
    if "comment" in data:
        order.comment = data["comment"]
    await session.commit()
    return {"id": order.id, "status": order.status}


def _order_dict(o: Order) -> dict:
    return {
        "id": o.id, "user_id": o.user_id, "total": o.total,
        "status": o.status, "status_label": ORDER_STATUSES.get(o.status, o.status),
        "comment": o.comment, "created_at": o.created_at.isoformat(),
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }
