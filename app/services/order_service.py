"""
Бизнес-логика заказов.
"""
import json
import logging
import os
import re
import uuid as uuid_mod
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.api.schemas.order import (
    OrderCreateRequest, OrderListResponse, OrderResponse, OrderItemResponse
)
from app.models.cart import Cart
from app.models.order import ORDER_STATUSES, Order, OrderItem
from app.models.product import Product
from app.models.product_stats import ProductStats
from app.models.user import User
from app.services.settings_service import get_shop_settings
from app.core.config import get_settings

logger = logging.getLogger(__name__)
_cfg = get_settings()

MEDIA_DIR = Path("/app/media")

ORDER_STATUS_MARKUP = {
    "inline_keyboard": [[{"text": "🏠 Перейти в меню", "callback_data": "menu_back"}]]
}


def _fmt_price(price: int | float) -> str:
    return f"{int(price):,} ₽".replace(",", " ")


def _order_to_response(o: Order, user: User | None = None, items: list | None = None) -> OrderResponse:
    user_name = user_contact = None
    if user:
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID:{o.user_id}"
        user_contact = f"@{user.username}" if user.username else None
    return OrderResponse(
        id=o.id, user_id=o.user_id, total=o.total,
        status=o.status, status_label=ORDER_STATUSES.get(o.status, o.status),
        comment=o.comment, delivery_address=getattr(o, "delivery_address", None),
        created_at=o.created_at, updated_at=o.updated_at,
        user_name=user_name, user_contact=user_contact, items=items,
    )


async def _send_telegram(chat_id, text: str, reply_markup=None) -> bool:
    if not _cfg.bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{_cfg.bot_token}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            if r.is_success and r.json().get("ok"):
                return True
            # fallback без HTML
            plain = {"chat_id": str(chat_id), "text": re.sub(r'<[^>]+>', '', text)}
            if reply_markup:
                plain["reply_markup"] = reply_markup
            r2 = await client.post(url, json=plain)
            return r2.is_success and r2.json().get("ok", False)
    except Exception as e:
        logger.warning("Telegram send error: %s", e)
    return False


async def _send_document_telegram(chat_id, file_path: str, caption: str = "", reply_markup=None) -> bool:
    if not _cfg.bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{_cfg.bot_token}/sendDocument"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
            with open(file_path, "rb") as f:
                r = await client.post(url, data=payload, files={"document": f})
            return r.is_success and r.json().get("ok", False)
    except Exception as e:
        logger.warning("Telegram send document error: %s", e)
    return False


async def list_orders(
    status: str | None, page: int, per_page: int, session: AsyncSession
) -> OrderListResponse:
    base_q = select(Order)
    count_q = select(func.count()).select_from(Order)
    if status:
        base_q = base_q.where(Order.status == status)
        count_q = count_q.where(Order.status == status)

    total = (await session.execute(count_q)).scalar() or 0
    offset = (page - 1) * per_page
    orders_res = await session.execute(
        base_q.order_by(Order.created_at.desc()).offset(offset).limit(per_page)
    )
    orders = orders_res.scalars().all()

    user_ids = {o.user_id for o in orders}
    user_map: dict = {}
    if user_ids:
        users_res = await session.execute(select(User).where(User.id.in_(user_ids)))
        user_map = {u.id: u for u in users_res.scalars().all()}

    items = [_order_to_response(o, user_map.get(o.user_id)) for o in orders]
    return OrderListResponse(
        items=items, total=total, page=page, per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


async def get_order(order_id: int, session: AsyncSession) -> OrderResponse:
    res = await session.execute(select(Order).where(Order.id == order_id))
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    items_res = await session.execute(
        select(OrderItem, Product)
        .outerjoin(Product, OrderItem.product_id == Product.id)
        .where(OrderItem.order_id == order_id)
    )
    items = [
        OrderItemResponse(
            product_id=item.product_id,
            name=item.name, price=item.price, quantity=item.quantity,
            sum=item.price * item.quantity,
            image_file_id=product.image_file_id if product else None,
            image_url=f"/media/{product.image_file_id}" if product and product.image_file_id else None,
        )
        for item, product in items_res.all()
    ]
    user_res = await session.execute(select(User).where(User.id == order.user_id))
    user = user_res.scalar_one_or_none()
    return _order_to_response(order, user, items)


async def get_user_orders(user_id: int, session: AsyncSession) -> list:
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    order_ids = [o.id for o in orders]
    items_map = {}
    if order_ids:
        items_res = await session.execute(
            select(OrderItem).where(OrderItem.order_id.in_(order_ids))
        )
        for item in items_res.scalars().all():
            items_map.setdefault(item.order_id, []).append(OrderItemResponse(
                product_id=item.product_id,
                name=item.name, price=item.price, quantity=item.quantity,
                sum=item.price * item.quantity,
            ))
    return [_order_to_response(o, items=items_map.get(o.id, [])) for o in orders]


async def create_order(data: OrderCreateRequest, session: AsyncSession) -> dict:
    user_id = data.user_id

    user_check = await session.execute(select(User).where(User.id == user_id))
    existing_user = user_check.scalar_one_or_none()
    if not existing_user:
        session.add(User(
            id=user_id, username=data.user_username,
            first_name=data.user_first_name, last_name=data.user_last_name,
        ))
    else:
        if data.user_username:
            existing_user.username = data.user_username
        if data.user_first_name:
            existing_user.first_name = data.user_first_name
        if data.user_last_name:
            existing_user.last_name = data.user_last_name
    await session.flush()

    result = await session.execute(
        select(Cart, Product)
        .join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id)
        .with_for_update(of=Product)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(400, "Cart is empty")

    total = sum(p.price * c.quantity for c, p in rows)
    order = Order(
        user_id=user_id, total=total, status="new",
        comment=data.comment, delivery_address=data.delivery_address,
    )
    session.add(order)
    await session.flush()

    items_text, stock_warnings = [], []
    for cart, product in rows:
        session.add(OrderItem(
            order_id=order.id, product_id=product.id,
            name=product.name, price=product.price, quantity=cart.quantity,
        ))
        await _inc_ordered(product.id, cart.quantity, session)
        if product.stock is not None and product.stock < cart.quantity:
            stock_warnings.append(
                f"⚠️ {product.name}: заказано {cart.quantity}, в наличии {product.stock}"
            )
        if product.stock is not None:
            product.stock = max(0, product.stock - cart.quantity)
        await session.delete(cart)
        items_text.append(f"• {product.name} × {cart.quantity} = {_fmt_price(product.price * cart.quantity)}")

    await session.commit()
    await session.refresh(order)

    user_res = await session.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    user_name = user_contact = ""
    if user:
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID:{user_id}"
        user_contact = f"@{user.username}" if user.username else f"tg://user?id={user_id}"

    shop = await get_shop_settings(session)
    admin_contact = shop.admin_contact or _cfg.admin_tg_id

    admin_text = (
        f"🆕 <b>Новый заказ #{order.id}</b>\n\n"
        f"👤 {user_name}\n📞 {user_contact}\n\n"
        f"🛒 Товары:\n" + "\n".join(items_text) + "\n\n"
        f"💰 <b>Итого: {_fmt_price(total)}</b>\n"
        + (f"🏠 Адрес: {data.delivery_address}\n" if data.delivery_address else "")
        + (f"💬 Комментарий: {data.comment}" if data.comment else "")
    )
    await _send_telegram(admin_contact, admin_text)

    if stock_warnings:
        await _send_telegram(admin_contact,
            f"⚠️ <b>Нехватка товара в заказе #{order.id}</b>\n\n" + "\n".join(stock_warnings))
        order.comment = (order.comment + "\n\n" if order.comment else "") + "\n".join(stock_warnings)
        await session.commit()
        await session.refresh(order)

    return {
        "id": order.id, "user_id": order.user_id, "total": order.total,
        "status": order.status, "created_at": order.created_at.isoformat(),
    }


async def update_order_status(
    order_id: int, new_status: str, comment: str | None, session: AsyncSession
) -> OrderResponse:
    if new_status not in ORDER_STATUSES:
        raise HTTPException(400, f"Invalid status: {new_status}")
    res = await session.execute(select(Order).where(Order.id == order_id))
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = new_status
    if comment is not None:
        order.comment = comment
    await session.commit()

    status_label = ORDER_STATUSES[new_status]
    await _send_telegram(
        order.user_id,
        f"📦 <b>Статус заказа #{order_id} изменён</b>\n\nНовый статус: {status_label}\nСумма: {_fmt_price(order.total)}",
        reply_markup=ORDER_STATUS_MARKUP,
    )
    shop = await get_shop_settings(session)
    admin_contact = shop.admin_contact or _cfg.admin_tg_id
    await _send_telegram(admin_contact, f"✅ Заказ #{order_id} → {status_label}")
    return _order_to_response(order)


async def _inc_ordered(product_id: int, qty: int, session: AsyncSession) -> None:
    res = await session.execute(select(ProductStats).where(ProductStats.product_id == product_id))
    s = res.scalar_one_or_none()
    if not s:
        s = ProductStats(product_id=product_id)
        session.add(s)
    s.ordered = (s.ordered or 0) + qty
