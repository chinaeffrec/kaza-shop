"""Роуты заказов — только HTTP-слой."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import require_auth
from app.api.schemas.order import (
    OrderCreateRequest, OrderListResponse, OrderResponse, OrderStatusUpdate, StatusItem,
)
from app.db.session import get_session
from app.models.order import ORDER_STATUSES
from app.services import order_service as svc
# receipt generation kept here as it has complex PDF + TG logic
from app.services.receipt_service import generate_and_send_receipt

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/statuses", response_model=list[StatusItem])
async def get_statuses():
    return [StatusItem(value=k, label=v) for k, v in ORDER_STATUSES.items()]


@router.post("/", summary="Создать заказ (вызывается ботом)")
async def create_order(
    data: OrderCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    return await svc.create_order(data, session)


@router.get("/user/{user_id}", summary="История заказов пользователя (для бота)")
async def get_user_orders(user_id: int, session: AsyncSession = Depends(get_session)):
    return await svc.get_user_orders(user_id, session)


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.list_orders(status, page, per_page, session)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.get_order(order_id, session)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.update_order_status(order_id, data.status, data.comment, session)


@router.post("/{order_id}/receipt")
async def send_receipt(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await generate_and_send_receipt(order_id, session)
