import logging
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.models.order import Order, OrderItem, ORDER_STATUSES
from app.models.cart import Cart
from app.models.product import Product
from app.models.product_stats import ProductStats
from app.models.user import User
from app.models.settings import ShopSettings

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TG_ID = os.getenv("ADMIN_TG_ID")  # Telegram ID администратора для уведомлений

MENU_REPLY_MARKUP = {
    "inline_keyboard": [
        [{"text": "🏠 В меню", "callback_data": "menu_back"}]
    ]
}

async def _send_telegram(chat_id: int | str, text: str, reply_markup: dict | None = None):
    """Отправляет сообщение через Telegram Bot API"""
    if not BOT_TOKEN or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            data = response.json()
            if response.is_success and data.get("ok"):
                return True

            description = data.get("description") if isinstance(data, dict) else response.text
            logger.warning("Telegram send failed chat_id=%s: %s", chat_id, description)

            fallback_payload = {"chat_id": str(chat_id), "text": re.sub(r'<[^>]+>', '', text)}
            if reply_markup:
                fallback_payload["reply_markup"] = reply_markup
            fallback_response = await client.post(url, json=fallback_payload)
            fallback_data = fallback_response.json()
            if fallback_response.is_success and fallback_data.get("ok"):
                return True
            fallback_description = fallback_data.get("description") if isinstance(fallback_data, dict) else fallback_response.text
            logger.warning("Telegram fallback failed chat_id=%s: %s", chat_id, fallback_description)
    except Exception as e:
        logger.exception("Telegram send error: %s", e)
    return False

async def _get_admin_contact(session: AsyncSession) -> str | None:
    """Возвращает admin_contact из настроек или ADMIN_TG_ID из env"""
    try:
        res = await session.execute(select(ShopSettings).where(ShopSettings.id == 1))
        s = res.scalar_one_or_none()
        if s and s.admin_contact:
            return s.admin_contact
    except Exception:
        pass
    return ADMIN_TG_ID

async def _inc_ordered(product_id: int, qty: int, session: AsyncSession):
    res = await session.execute(
        select(ProductStats).where(ProductStats.product_id == product_id)
    )
    s = res.scalar_one_or_none()
    if not s:
        s = ProductStats(product_id=product_id)
        session.add(s)
    s.ordered += qty


# ВАЖНО: /statuses и /user/{user_id} ДОЛЖНЫ быть ДО /{order_id}
@router.get("/statuses")
async def get_statuses():
    return [{"value": k, "label": v} for k, v in ORDER_STATUSES.items()]


@router.get("/user/{user_id}")
async def get_user_orders(user_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    return [_order_dict(o) for o in result.scalars().all()]


@router.post("/")
async def create_order(data: dict, session: AsyncSession = Depends(get_session)):
    user_id = data["user_id"]
    comment = data.get("comment", "")
    delivery_address = data.get("delivery_address", "")

    result = await session.execute(
        select(Cart, Product).join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total = sum(p.price * c.quantity for c, p in rows)
    order = Order(
        user_id=user_id,
        total=total,
        status="new",
        comment=comment,
        delivery_address=delivery_address,
    )
    session.add(order)
    await session.flush()

    items_text = []
    for cart, product in rows:
        session.add(OrderItem(
            order_id=order.id, product_id=product.id,
            name=product.name, price=product.price, quantity=cart.quantity,
        ))
        await _inc_ordered(product.id, cart.quantity, session)
        await session.delete(cart)
        items_text.append(f"• {product.name} × {cart.quantity} = {product.price * cart.quantity} ₽")

    await session.commit()
    await session.refresh(order)

    # Получаем данные пользователя для уведомления
    user_res = await session.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    user_name = ""
    user_contact = ""
    if user:
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID:{user_id}"
        user_contact = f"@{user.username}" if user.username else f"tg://user?id={user_id}"

    # Уведомление администратору
    admin_text = (
        f"🆕 <b>Новый заказ #{order.id}</b>\n\n"
        f"👤 Покупатель: {user_name}\n"
        f"📞 Контакт: {user_contact}\n\n"
        f"🛒 Товары:\n" + "\n".join(items_text) + "\n\n"
        f"💰 <b>Итого: {total} ₽</b>\n"
        + (f"🏠 Адрес: {delivery_address}\n" if delivery_address else "")
        + (f"💬 Комментарий: {comment}" if comment else "")
    )
    admin_contact = await _get_admin_contact(session)
    await _send_telegram(admin_contact, admin_text)

    return {
        "id": order.id, "user_id": order.user_id,
        "total": order.total, "status": order.status,
        "created_at": order.created_at.isoformat(),
    }


@router.get("/")
async def list_orders(status: str | None = None, session: AsyncSession = Depends(get_session)):
    query = select(Order).order_by(Order.created_at.desc())
    if status:
        query = query.where(Order.status == status)
    result = await session.execute(query)
    orders = result.scalars().all()

    # Обогащаем данными пользователей
    result_list = []
    for o in orders:
        d = _order_dict(o)
        user_res = await session.execute(select(User).where(User.id == o.user_id))
        user = user_res.scalar_one_or_none()
        if user:
            d["user_name"] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID:{o.user_id}"
            d["user_contact"] = f"@{user.username}" if user.username else None
        else:
            d["user_name"] = f"ID:{o.user_id}"
            d["user_contact"] = None
        result_list.append(d)
    return result_list


@router.get("/{order_id}")
async def get_order(order_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items_result = await session.execute(
        select(OrderItem, Product)
        .outerjoin(Product, OrderItem.product_id == Product.id)
        .where(OrderItem.order_id == order_id)
    )
    items = items_result.all()

    d = _order_dict(order)
    d["items"] = [
        {
            "product_id": item.product_id,
            "name": item.name,
            "price": item.price,
            "quantity": item.quantity,
            "sum": item.price * item.quantity,
            "image_file_id": product.image_file_id if product else None,
            "image_url": f"/media/{product.image_file_id}" if product and product.image_file_id else None,
        }
        for item, product in items
    ]

    user_res = await session.execute(select(User).where(User.id == order.user_id))
    user = user_res.scalar_one_or_none()
    if user:
        d["user_name"] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID:{order.user_id}"
        d["user_contact"] = f"@{user.username}" if user.username else None
    return d


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

    # Уведомление покупателю
    status_label = ORDER_STATUSES.get(new_status, new_status)
    buyer_text = (
        f"📦 <b>Статус заказа #{order_id} изменён</b>\n\n"
        f"Новый статус: {status_label}\n\n"
        f"Сумма заказа: {order.total} ₽"
    )
    await _send_telegram(order.user_id, buyer_text, reply_markup=MENU_REPLY_MARKUP)

    # Уведомление администратору
    admin_text = f"✅ Заказ #{order_id} → статус: {status_label}"
#    await _send_telegram(ADMIN_TG_ID, admin_text)
    admin_contact = await _get_admin_contact(session)
    await _send_telegram(admin_contact, admin_text)

    return {"id": order.id, "status": order.status}


def _order_dict(o: Order) -> dict:
    return {
        "id": o.id, "user_id": o.user_id, "total": o.total,
        "status": o.status, "status_label": ORDER_STATUSES.get(o.status, o.status),
        "comment": o.comment,
        "delivery_address": getattr(o, "delivery_address", None),
        "created_at": o.created_at.isoformat(),
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }
