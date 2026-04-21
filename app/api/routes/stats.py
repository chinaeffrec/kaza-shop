from datetime import datetime, date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.db.session import get_session
from app.models.product_stats import ProductStats
from app.models.order import Order, OrderItem

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


@router.get("/products")
async def get_all_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(select(ProductStats))
    stats = {s.product_id: s for s in res.scalars().all()}

    # Продажи за период
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
