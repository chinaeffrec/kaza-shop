from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.db.session import get_session
from app.models.product_stats import ProductStats
from app.models.order import Order, OrderItem, ORDER_STATUSES
from app.models.product import Product

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
    """Сводный дашборд: выручка, заказы, топ товаров"""

    # Базовый запрос заказов
    orders_q = select(Order)
    if date_from:
        orders_q = orders_q.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        orders_q = orders_q.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    orders_res = await session.execute(orders_q)
    all_orders = orders_res.scalars().all()

    total_revenue = sum(o.total for o in all_orders if o.status not in ("cancelled", "returned"))
    total_orders = len(all_orders)
    by_status = {}
    for o in all_orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1

    # Топ товаров — по выручке и по количеству
    items_q = (
        select(
            OrderItem.product_id,
            OrderItem.name,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.price * OrderItem.quantity).label("total_sum"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.status.not_in(["cancelled", "returned"]))
        .group_by(OrderItem.product_id, OrderItem.name)
    )
    if date_from:
        items_q = items_q.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        items_q = items_q.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    items_res = await session.execute(items_q)
    items_rows = items_res.all()

    top_by_revenue = sorted(items_rows, key=lambda r: r.total_sum or 0, reverse=True)[:10]
    top_by_qty = sorted(items_rows, key=lambda r: r.total_qty or 0, reverse=True)[:10]

    return {
        "period": {"from": date_from, "to": date_to},
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "orders_by_status": [
            {"status": k, "label": ORDER_STATUSES.get(k, k), "count": v}
            for k, v in by_status.items()
        ],
        "top_by_revenue": [
            {"product_id": r.product_id, "name": r.name,
             "total_qty": r.total_qty, "total_sum": r.total_sum}
            for r in top_by_revenue
        ],
        "top_by_qty": [
            {"product_id": r.product_id, "name": r.name,
             "total_qty": r.total_qty, "total_sum": r.total_sum}
            for r in top_by_qty
        ],
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
