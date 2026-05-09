"""Роуты статистики — только HTTP-слой."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import require_auth
from app.api.schemas.stats import DashboardResponse, ProductStatsResponse
from app.db.session import get_session
from app.services import stats_service as svc

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.get_dashboard(date_from, date_to, session)


@router.get("/export")
async def export_orders(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    output = await svc.export_orders_xlsx(date_from, date_to, status, session)
    filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/products", response_model=ProductStatsResponse)
async def get_product_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.get_product_stats(date_from, date_to, session)


@router.get("/products/export")
async def export_product_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    output = await svc.export_product_stats_xlsx(date_from, date_to, session)
    filename = f"stats_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/products/{product_id}/return")
async def track_return(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.track_return(product_id, session)
