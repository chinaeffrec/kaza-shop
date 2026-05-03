import httpx
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.keyboards.menu import main_menu
from app.bot.services.bot_messages import clear_and_reset, track
from app.bot.services.navigation import navigation
from app.bot.services.render_engine import render_engine
from app.bot.states.screen import Screen

router = Router()
BASE_URL = "http://app:8000"


class CheckoutState(StatesGroup):
    waiting_comment = State()
    waiting_address = State()


async def _replace_with_text(message: Message, text: str, reply_markup=None, parse_mode=None):
    try:
        if message.photo or message.document:
            try:
                await message.delete()
            except Exception:
                pass
            sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
            track(message.chat.id, sent.message_id)
        else:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        track(message.chat.id, sent.message_id)


def build_cart_text(data: dict) -> str:
    lines = ["🛒 <b>Ваша корзина</b>\n"]
    for item in data["items"]:
        lines.append(f"• {item['name']} × {item['quantity']} = {_fmt_price(item['sum'])}")
    lines.append(f"\n<b>Итого: {_fmt_price(data['total'])}</b>")
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
    rows.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fmt_price(price: int | float) -> str:
    if isinstance(price, float) and price != int(price):
        return f"{price:,.2f} ₽".replace(",", " ")
    return f"{int(price):,} ₽".replace(",", " ")


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
        response = await client.get(f"{BASE_URL}/cart/{user_id}")
    data = response.json()

    if not data.get("items"):
        await _replace_with_text(
            callback.message,
            "🛒 Ваша корзина пуста",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
            ])
        )
    else:
        await _replace_with_text(
            callback.message,
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
        response = await client.get(f"{BASE_URL}/orders/user/{user_id}")
    orders = response.json()

    active = [o for o in orders if o["status"] not in ("delivered", "cancelled", "returned")]
    done = [o for o in orders if o["status"] in ("delivered",)]

    if not orders:
        text = "📦 У вас пока нет заказов."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
        ])
    else:
        lines = ["📦 <b>Активные заказы</b>\n"] if active else ["📦 Активных заказов нет.\n"]
        for o in active:
            status_label = o.get("status_label", o["status"])
            order_text = f"📦 Заказ #{o['id']}\n"
            if o.get("items"):
                for it in o["items"]:
                    order_text += f"  • {it['name']} × {it['quantity']} = {_fmt_price(it['sum'])}\n"
            order_text += (
                f"💰 <b>Итого: {_fmt_price(o['total'])}</b>\n"
                f"Статус: <b>{status_label}</b> · {o['created_at'][:10]}"
            )
            lines.append(order_text)
        text = "\n\n".join(lines)

        kb_rows = []
        if done:
            kb_rows.append([InlineKeyboardButton(text=f"📋 История заказов ({len(done)})", callback_data="order_history")])
        kb_rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await _replace_with_text(callback.message, text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "order_history")
async def order_history(callback: CallbackQuery):
    import httpx
    user_id = callback.from_user.id
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/orders/user/{user_id}")
    orders = response.json()
    done = [o for o in orders if o["status"] == "delivered"]

    if not done:
        text = "📋 История заказов пуста."
    else:
        lines = ["📋 <b>История заказов</b>\n"]
        for o in done:
            order_text = f"✔️ Заказ #{o['id']}\n"
            if o.get("items"):
                for it in o["items"]:
                    order_text += f"  • {it['name']} × {it['quantity']} = {_fmt_price(it['sum'])}\n"
            order_text += f"💰 {_fmt_price(o['total'])} · {o['created_at'][:10]}"
            lines.append(order_text)
        text = "\n\n".join(lines)

    await _replace_with_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Мои заказы", callback_data="menu_order")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_question")
async def open_question(callback: CallbackQuery):
    import httpx
    contact = "@support"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{BASE_URL}/settings/")
            if r.status_code == 200:
                contact = r.json().get("seller_contact") or contact
    except Exception:
        pass
    await _replace_with_text(
        callback.message,
        f"💬 <b>Написать нам</b>\n\nСвяжитесь с нами напрямую:\n{contact}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery, state: FSMContext):
    import httpx
    navigation.reset(callback.from_user.id)
    await state.clear()
    welcome_text = "👋 Добро пожаловать!\n\nВыберите действие:"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{BASE_URL}/settings/")
            if r.status_code == 200:
                welcome_text = r.json().get("welcome_message") or welcome_text
    except Exception:
        pass
    await _replace_with_text(callback.message, welcome_text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CheckoutState.waiting_comment)
    await _replace_with_text(
        callback.message,
        "💬 Оставьте комментарий к заказу\n(или нажмите кнопку «Пропустить»):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="checkout_skip_comment")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "checkout_skip_comment")
async def checkout_skip_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment="")
    await state.set_state(CheckoutState.waiting_address)
    await _replace_with_text(
        callback.message,
        "🏠 Укажите адрес доставки\n(или нажмите кнопку «Пропустить»):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="checkout_skip_address")]
        ])
    )
    await callback.answer()


@router.message(CheckoutState.waiting_comment, F.text)
async def checkout_comment(message: Message, state: FSMContext):
    comment = "" if message.text == "/skip" else message.text
    await state.update_data(comment=comment)
    await state.set_state(CheckoutState.waiting_address)
    await message.answer(
        "🏠 Укажите адрес доставки\n(или нажмите кнопку «Пропустить»):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="checkout_skip_address")]
        ])
    )


@router.message(CheckoutState.waiting_address, F.text)
async def checkout_address(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    if address == "/skip":
        address = ""
    await _finalize_order(message, state, address)


@router.callback_query(F.data == "checkout_skip_address")
async def checkout_skip_address(callback: CallbackQuery, state: FSMContext):
    await _finalize_order(callback.message, state, "")
    await callback.answer()


@router.message(CheckoutState.waiting_comment)
async def checkout_comment_non_text(message: Message):
    await message.answer(
        "💬 Комментарий можно отправить только текстом.\nИли нажмите кнопку «Пропустить».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="checkout_skip_comment")]
        ])
    )


@router.message(CheckoutState.waiting_address)
async def checkout_address_non_text(message: Message):
    await message.answer(
        "🏠 Адрес доставки можно отправить только текстом.\nИли нажмите кнопку «Пропустить».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="checkout_skip_comment")]
        ])
    )


async def _finalize_order(message, state: FSMContext, address: str):

    data = await state.get_data()
    comment = data.get("comment", "")
    user_id = message.chat.id
    await state.clear()

    async with httpx.AsyncClient() as client:
        cart_resp = await client.get(f"{BASE_URL}/cart/{user_id}")
    cart_data = cart_resp.json()
    total = cart_data.get("total", 0)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/orders/",
            json={
                "user_id": user_id,
                "comment": comment,
                "delivery_address": address,
                "user_first_name": message.chat.first_name or "",
                "user_last_name": message.chat.last_name or "",
                "user_username": message.chat.username or "",
            }
        )

    if response.status_code != 200:
        await message.answer("❌ Ошибка при оформлении заказа.", reply_markup=main_menu())
        return

    order = response.json()
    caption = (
        f"✅ <b>Заказ #{order['id']} оформлен!</b>\n\n"
        f"Сумма: {_fmt_price(order['total'])}\n"
        f"Статус: 🆕 Новый\n"
    )
    if address:
        caption += f"📍 Адрес: {address}\n"
    if comment:
        caption += f"💬 Комментарий: {comment}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Связаться с продавцом", callback_data="menu_question")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")],
    ])

    qr_url = None
    qr_comment = ""
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{BASE_URL}/settings/")
            if r.status_code == 200:
                cfg = r.json()
                qr_url = cfg.get("payment_qr_url")
                qr_comment = cfg.get("payment_qr_comment", "").strip()
    except Exception:
        pass

    if qr_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                img_resp = await client.get(f"{BASE_URL}{qr_url}")
                if img_resp.status_code == 200 and img_resp.content and len(img_resp.content) > 100:
                    caption_for_qr = caption + f"\n📱 <b>Оплатите {_fmt_price(total)} по QR-коду:</b>"
                    if qr_comment:
                        caption_for_qr += f"\n{qr_comment}"
                    qr_photo = BufferedInputFile(img_resp.content, filename="qr.png")
                    await message.answer_photo(
                        photo=qr_photo,
                        caption=caption_for_qr,
                        reply_markup=kb,
                        parse_mode="HTML",
                    )
                    return
        except Exception:
            pass

    caption += "\nДля оплаты свяжитесь с продавцом."
    await message.answer(caption, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "menu_refresh")
async def menu_refresh(callback: CallbackQuery, state: FSMContext):
    navigation.reset(callback.from_user.id)
    await state.clear()

    welcome_text = "👋 Добро пожаловать!\n\nВыберите действие:"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{BASE_URL}/settings/")
            if r.status_code == 200:
                welcome_text = r.json().get("welcome_message") or welcome_text
    except Exception:
        pass

    await clear_and_reset(callback.from_user.id, callback.bot)

    sent = await callback.bot.send_message(
        callback.from_user.id,
        welcome_text,
        reply_markup=main_menu(),
    )
    track(callback.from_user.id, sent.message_id)
    await callback.answer("Чат очищен")

@router.callback_query(F.data.startswith("noop_"))
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.message(StateFilter(None), F.text)
async def unexpected_message(message: Message):
    if message.text and message.text.startswith('/'):
        return
    await message.answer(
        "ℹ️ Бот принимает свободный текст только там, где сам его запрашивает.\n"
        "В остальных случаях используйте кнопки меню.",
        reply_markup=main_menu()
    )
