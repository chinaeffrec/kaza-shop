from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.db.session import get_session
from app.models.product_stats import ProductStats
from app.models.order import Order, OrderItem, ORDER_STATUSES
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


async def ensure_stats(product_id: int, session: AsyncSession) -> ProductStats:
    res = await session.execute(
        select(ProductStats).where(ProductStats.product_id == product_id)
    )
    s = res.scalar_one_or_none()
    if not s:
        s = ProductStats(product_id=product_id)
        session.add(s)
        await session.flush()
    return s


@router.get("/dashboard")
async def get_dashboard(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Сводный дашборд по заказам: выручка, статусы, последние заказы"""

    # Базовый запрос заказов
    orders_q = select(Order).order_by(Order.created_at.desc())
    if date_from:
        orders_q = orders_q.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        orders_q = orders_q.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    orders_res = await session.execute(orders_q)
    all_orders = orders_res.scalars().all()

    billable_orders = [o for o in all_orders if o.status not in ("cancelled", "returned")]
    total_revenue = sum(o.total for o in billable_orders)
    total_orders = len(all_orders)
    billable_orders_count = len(billable_orders)
    average_order_value = int(total_revenue / billable_orders_count) if billable_orders_count else 0
    by_status = {}
    for o in all_orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1

    user_map = {}
    user_ids = {o.user_id for o in all_orders}
    if user_ids:
        users_res = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = users_res.scalars().all()
        user_map = {u.id: u for u in users}

    status_order = list(ORDER_STATUSES.keys())
    sorted_statuses = [s for s in status_order if s in by_status] + [s for s in by_status if s not in status_order]

    recent_orders = []
    for order in all_orders[:10]:
        user = user_map.get(order.user_id)
        user_name = f"ID:{order.user_id}"
        if user:
            user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or user_name

        recent_orders.append({
            "id": order.id,
            "user_id": order.user_id,
            "user_name": user_name,
            "status": order.status,
            "status_label": ORDER_STATUSES.get(order.status, order.status),
            "total": order.total,
            "comment": order.comment,
            "delivery_address": order.delivery_address,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        })

    return {
        "period": {"from": date_from, "to": date_to},
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "billable_orders": billable_orders_count,
        "average_order_value": average_order_value,
        "orders_by_status": [
            {"status": status, "label": ORDER_STATUSES.get(status, status), "count": by_status[status]}
            for status in sorted_statuses
        ],
        "recent_orders": recent_orders,
    }


@router.get("/products")
async def get_all_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(select(ProductStats))
    stats = {s.product_id: s for s in res.scalars().all()}

    query = select(
        OrderItem.product_id,
        func.sum(OrderItem.quantity).label("sold_qty"),
        func.sum(OrderItem.price * OrderItem.quantity).label("sold_sum"),
    ).join(Order, OrderItem.order_id == Order.id).group_by(OrderItem.product_id)

    if date_from:
        query = query.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    period_res = await session.execute(query)
    period = {row.product_id: {"sold_qty": row.sold_qty, "sold_sum": row.sold_sum}
              for row in period_res.all()}

    result = []
    all_pids = set(stats) | set(period)
    for pid in all_pids:
        s = stats.get(pid)
        p = period.get(pid, {})
        result.append({
            "product_id": pid,
            "added_to_cart": s.added_to_cart if s else 0,
            "ordered": s.ordered if s else 0,
            "returned": s.returned if s else 0,
            "period_sold_qty": p.get("sold_qty", 0),
            "period_sold_sum": p.get("sold_sum", 0),
        })
    return result


@router.post("/products/{product_id}/cart_add")
async def track_cart_add(product_id: int, session: AsyncSession = Depends(get_session)):
    s = await ensure_stats(product_id, session)
    s.added_to_cart += 1
    await session.commit()
    return {"ok": True}


@router.post("/products/{product_id}/return")
async def track_return(product_id: int, session: AsyncSession = Depends(get_session)):
    s = await ensure_stats(product_id, session)
    s.returned += 1
    await session.commit()
    return {"ok": True}
