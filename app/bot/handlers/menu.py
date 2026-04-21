from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.services.navigation import navigation
from app.bot.states.screen import Screen
from app.bot.services.render_engine import render_engine

router = Router()


# ─────────────────────────────────────────
# Helpers (используются в cart_actions.py)
# ─────────────────────────────────────────

def build_cart_text(data: dict) -> str:
    lines = ["🛒 <b>Ваша корзина</b>\n"]
    for item in data["items"]:
        lines.append(f"• {item['name']} × {item['quantity']} = {item['sum']} ₽")
    lines.append(f"\n<b>Итого: {data['total']} ₽</b>")
    return "\n".join(lines)


def build_cart_keyboard(data: dict) -> InlineKeyboardMarkup:
    rows = []
    for item in data["items"]:
        pid = item["product_id"]
        rows.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{pid}"),
            InlineKeyboardButton(text=item["name"], callback_data=f"noop_{pid}"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"rm_{pid}"),
        ])
    rows.append([
        InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout"),
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────

@router.callback_query(F.data == "menu_catalog")
async def open_catalog(callback: CallbackQuery):
    user_id = callback.from_user.id
    navigation.reset(user_id)
    screen = Screen(type="categories")
    navigation.push(user_id, screen)
    await render_engine.render(screen, callback.message)
    await callback.answer()


@router.callback_query(F.data == "menu_cart")
async def open_cart(callback: CallbackQuery):
    import httpx
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://app:8000/cart/{user_id}")
    data = response.json()

    if not data.get("items"):
        await callback.message.edit_text(
            "🛒 Ваша корзина пуста",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
            ])
        )
    else:
        await callback.message.edit_text(
            build_cart_text(data),
            reply_markup=build_cart_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "menu_order")
async def open_order_status(callback: CallbackQuery):
    import httpx
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://app:8000/orders/user/{user_id}")
    orders = response.json()

    if not orders:
        text = "📦 У вас пока нет заказов."
    else:
        lines = ["📦 <b>Ваши заказы</b>\n"]
        status_emoji = {
            "new": "🆕",
            "confirmed": "✅",
            "shipped": "🚚",
            "delivered": "✔️",
            "cancelled": "❌",
        }
        for o in orders:
            emoji = status_emoji.get(o["status"], "❓")
            lines.append(
                f"{emoji} Заказ #{o['id']} — {o['total']} ₽\n"
                f"   Статус: <b>{o['status']}</b>\n"
                f"   {o['created_at'][:10]}"
            )
        text = "\n\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_question")
async def open_question(callback: CallbackQuery):
    import httpx
    contact = "@support"  # fallback
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get("http://app:8000/settings/")
            if r.status_code == 200:
                contact = r.json().get("seller_contact") or contact
    except Exception:
        pass

    await callback.message.edit_text(
        f"💬 <b>Написать нам</b>\n\nСвяжитесь с нами напрямую:\n{contact}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery):
    import httpx
    from app.bot.keyboards.menu import main_menu
    navigation.reset(callback.from_user.id)

    welcome_text = "👋 Добро пожаловать!\n\nВыберите действие:"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get("http://app:8000/settings/")
            if r.status_code == 200:
                welcome_text = r.json().get("welcome_message") or welcome_text
    except Exception:
        pass

    await callback.message.edit_text(welcome_text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    import httpx
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://app:8000/orders/",
            json={"user_id": user_id}
        )

    if response.status_code == 200:
        order = response.json()
        await callback.message.edit_text(
            f"✅ <b>Заказ #{order['id']} оформлен!</b>\n\n"
            f"Сумма: {order['total']} ₽\n"
            f"Статус: 🆕 Новый\n\n"
            f"Продавец свяжется с вами в ближайшее время.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.answer("Ошибка при оформлении заказа", show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("noop_"))
async def noop(callback: CallbackQuery):
    await callback.answer()
