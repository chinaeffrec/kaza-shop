import logging
import re
import os
import uuid as uuid_mod
from pathlib import Path as FilePath

import httpx
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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

MEDIA_DIR_RECEIPT = FilePath("/app/media")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TG_ID = os.getenv("ADMIN_TG_ID")  # Telegram ID администратора для уведомлений

MENU_REPLY_MARKUP = {
    "inline_keyboard": [
        [{"text": "🏠 В меню", "callback_data": "menu_back"}]
    ]
}

DEJAVU_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if os.path.exists(DEJAVU_PATH):
    pdfmetrics.registerFont(TTFont('DejaVu', DEJAVU_PATH))
    pdfmetrics.registerFont(TTFont('DejaVuBold', DEJAVU_BOLD_PATH))
    FONT_NAME = 'DejaVu'
    FONT_BOLD = 'DejaVuBold'
else:
    FONT_NAME = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'

async def _send_document_telegram(chat_id: int | str, file_path: str, caption: str = ""):
    """Отправляет PDF-файл через Telegram Bot API."""
    if not BOT_TOKEN or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    url,
                    data={"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"},
                    files={"document": f},
                )
            return response.is_success and response.json().get("ok", False)
    except Exception as e:
        logger.exception("Telegram send document error: %s", e)
    return False

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

    # Авторегистрация / обновление пользователя
    user_check = await session.execute(select(User).where(User.id == user_id))
    existing_user = user_check.scalar_one_or_none()
    if not existing_user:
        session.add(User(
            id=user_id,
            username=data.get("user_username"),
            first_name=data.get("user_first_name"),
            last_name=data.get("user_last_name"),
        ))
    else:
        # Обновляем если изменились
        if data.get("user_username"):
            existing_user.username = data["user_username"]
        if data.get("user_first_name"):
            existing_user.first_name = data["user_first_name"]
        if data.get("user_last_name"):
            existing_user.last_name = data["user_last_name"]
    await session.flush()

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
    stock_warnings = []
    for cart, product in rows:
        session.add(OrderItem(
            order_id=order.id, product_id=product.id,
            name=product.name, price=product.price, quantity=cart.quantity,
        ))
        await _inc_ordered(product.id, cart.quantity, session)

        # Проверяем остаток
        if product.stock is not None and product.stock < cart.quantity:
            stock_warnings.append(
                f"⚠️ {product.name}: заказано {cart.quantity}, в наличии {product.stock}"
            )

        # Уменьшаем остаток
        if product.stock is not None:
            product.stock = max(0, product.stock - cart.quantity)

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

    if stock_warnings:
        await _send_telegram(admin_contact,
                             f"⚠️ <b>Нехватка товара в заказе #{order.id}</b>\n\n" + "\n".join(stock_warnings))
        # Дублируем в комментарий для отображения в админке
        order.comment = (order.comment + "\n\n" if order.comment else "") + "⚠️ НЕХВАТКА ТОВАРА:\n" + "\n".join(
            stock_warnings)
        await session.commit()
        await session.refresh(order)

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


@router.post("/{order_id}/receipt")
async def generate_and_send_receipt(order_id: int, session: AsyncSession = Depends(get_session)):
    """Генерирует PDF товарного чека и отправляет покупателю."""
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    # Получаем состав заказа
    items_result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    items = items_result.scalars().all()

    # Данные покупателя
    user_result = await session.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one_or_none()

    # Настройки магазина
    settings_result = await session.execute(select(ShopSettings).where(ShopSettings.id == 1))
    shop = settings_result.scalar_one_or_none()

    shop_name = shop.shop_name if shop else "Kaza Shop"
    seller_contact = shop.seller_contact if shop else ""
    legal_name = shop.legal_name if shop else ""
    stamp_file = shop.stamp_filename if shop else None

    buyer_name = ""
    if user:
        buyer_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"ID:{order.user_id}"

    # Генерируем PDF
    receipt_id = uuid_mod.uuid4().hex[:8]
    filename = f"receipt_{order_id}_{receipt_id}.pdf"
    filepath = MEDIA_DIR_RECEIPT / filename
    MEDIA_DIR_RECEIPT.mkdir(parents=True, exist_ok=True)

    c = pdf_canvas.Canvas(str(filepath), pagesize=A5)
    width, height = A5

    y = height - 15 * mm

    def draw_line(text, font=FONT_NAME, size=10, y_offset=6):
        nonlocal y
        c.setFont(font, size)
        c.drawString(15 * mm, y, text)
        y -= y_offset * mm

    # Заголовок
    c.setFont(FONT_BOLD, 14)
    c.drawString(15 * mm, y, f"{shop_name}")
    y -= 8 * mm
    c.setFont(FONT_BOLD, 12)
    c.drawString(15 * mm, y, f"Товарный чек №{order.id}")
    y -= 6 * mm
    c.setFont(FONT_NAME, 9)
    c.drawString(15 * mm, y, f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}" if order.created_at else f"Дата: —")
    y -= 5 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 5 * mm

    # Покупатель
    c.setFont(FONT_BOLD, 10)
    c.drawString(15 * mm, y, "Покупатель:")
    y -= 5 * mm
    c.setFont(FONT_NAME, 10)
    c.drawString(15 * mm, y, buyer_name if buyer_name else f"ID: {order.user_id}")
    if order.delivery_address:
        y -= 5 * mm
        c.drawString(15 * mm, y, f"Адрес: {order.delivery_address}")
    y -= 7 * mm

    # Таблица товаров
    c.setFont(FONT_BOLD, 9)
    c.drawString(15 * mm, y, "Товар")
    c.drawString(85 * mm, y, "Цена")
    c.drawString(110 * mm, y, "Кол-во")
    c.drawString(125 * mm, y, "Сумма")
    y -= 5 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 3 * mm

    c.setFont(FONT_NAME, 9)
    for item in items:
        c.drawString(15 * mm, y, item.name[:40])
        c.drawString(85 * mm, y, f"{item.price} ₽")
        c.drawString(110 * mm, y, str(item.quantity))
        c.drawString(125 * mm, y, f"{item.price * item.quantity} ₽")
        y -= 5 * mm

    y -= 2 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 5 * mm
    c.setFont(FONT_BOLD, 11)
    c.drawString(15 * mm, y, f"Итого: {order.total} ₽")
    y -= 5 * mm
    c.setFont(FONT_NAME, 9)
    status_label = ORDER_STATUSES.get(order.status, order.status)
    c.drawString(15 * mm, y, f"Статус: {status_label}")
    y -= 8 * mm

    # Продавец
    c.setFont(FONT_BOLD, 9)
    c.drawString(15 * mm, y, "Продавец:")
    y -= 5 * mm
    c.setFont(FONT_NAME, 9)
    seller_label = shop.legal_name or seller_contact or shop_name or "Kaza Shop"
    c.drawString(15 * mm, y, seller_label)
    y -= 8 * mm

    # Печать
    if stamp_file:
        stamp_path = MEDIA_DIR_RECEIPT / stamp_file
        if stamp_path.exists():
            try:
                c.drawImage(str(stamp_path), width - 40 * mm, y - 15 * mm, width=25 * mm, height=25 * mm, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

    y -= 12 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 6 * mm
    c.setFont(FONT_NAME, 8)
    c.drawString(15 * mm, y, "Спасибо за покупку!")
    c.drawRightString(width - 15 * mm, y, f"Чек сформирован: {order.created_at.strftime('%d.%m.%Y') if order.created_at else '—'}")

    c.save()

    # Отправляем покупателю
    caption = f"🧾 <b>Чек по заказу #{order.id}</b>\nСумма: {order.total} ₽\nСпасибо за покупку!"
    sent = await _send_document_telegram(order.user_id, str(filepath), caption)

    return {
        "status": "ok",
        "receipt_url": f"/media/{filename}",
        "sent_to_buyer": sent,
    }

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
