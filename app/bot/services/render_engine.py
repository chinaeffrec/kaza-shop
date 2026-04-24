import logging
from pathlib import Path

import httpx
from aiogram.types import (
    BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Message
)

from app.bot.services.catalog_cache import catalog_cache
from app.bot.keyboards.catalog import categories_kb, subcategories_kb

BASE_URL = "http://app:8000"
MEDIA_DIR = Path(__file__).resolve().parents[2] / "media"
logger = logging.getLogger(__name__)


def _fmt_price(price) -> str:
    if price is None:
        return "—"
    try:
        price = float(price)
    except (TypeError, ValueError):
        return str(price)
    if price != int(price):
        whole = int(price)
        frac_str = f"{price:.2f}"[len(str(whole)):]
        whole_str = f"{whole:,}".replace(",", " ")
        return f"{whole_str}{frac_str} ₽"
    return f"{int(price):,}".replace(",", " ") + " ₽"


def _product_kb(product, idx: int, total: int, products: list) -> InlineKeyboardMarkup:
    """Клавиатура карточки товара с навигацией"""
    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"open_product_{products[idx-1].id}"))
    nav_row.append(InlineKeyboardButton(text=f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"open_product_{products[idx+1].id}"))

    return InlineKeyboardMarkup(inline_keyboard=[
        nav_row,
        [
            InlineKeyboardButton(text="🛒 В корзину", callback_data=f"cart_add_{product.id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
        ],
    ])


def _product_caption(product) -> str:
    lines = [f"<b>{product.name}</b>"]
    if getattr(product, "discount_price", None):
        lines.append(f"💰 <s>{_fmt_price(product.price)}</s> → <b>{_fmt_price(product.discount_price)}</b>")
    else:
        lines.append(f"💰 <b>{_fmt_price(product.price)}</b>")
    # Сначала характеристики, потом описание
    if product.characteristics:
        lines.append(f"\n📋 {product.characteristics}")
    if product.description:
        lines.append(f"\n{product.description}")
    return "\n".join(lines)


async def _edit_to_text(message: Message, text: str, kb: InlineKeyboardMarkup):
    """Редактирует сообщение в текстовое. Работает и если сообщение с фото."""
    try:
        if message.photo or message.document:
            try:
                await message.delete()
            except Exception:
                pass
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


async def _send_photo_message(message: Message, photo_path: Path, caption: str, kb: InlineKeyboardMarkup):
    photo = BufferedInputFile(photo_path.read_bytes(), filename=photo_path.name)
    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=kb,
        parse_mode="HTML",
    )


async def _edit_to_photo(message: Message, photo_path: Path, caption: str, kb: InlineKeyboardMarkup):
    """Показывает фото товара отдельным сообщением для максимально надёжной доставки."""
    if not photo_path.exists():
        logger.warning("Photo not found: %s", photo_path)
        await _edit_to_text(message, caption, kb)
        return

    try:
        try:
            await message.delete()
        except Exception:
            pass
        await _send_photo_message(message, photo_path, caption, kb)
    except Exception:
        try:
            await _send_photo_message(message, photo_path, caption, kb)
        except Exception:
            await _edit_to_text(message, caption, kb)


async def render_product_card(message: Message, product, idx: int, total: int):
    """Публичная функция — вызывается из catalog.py для стрелок-навигации"""
    sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
    products = sub.products if sub else [product]
    kb = _product_kb(product, idx, total, products)
    caption = _product_caption(product)

    if product.image:
        await _edit_to_photo(message, MEDIA_DIR / product.image, caption, kb)
    else:
        await _edit_to_text(message, caption, kb)


class RenderEngine:

    async def render(self, screen, message: Message):

        if screen.type == "categories":
            categories = catalog_cache.get_categories()
            await _edit_to_text(
                message,
                "🗂 <b>Каталог</b>\n\nВыберите категорию:",
                categories_kb(categories),
            )

        elif screen.type == "subcategories":
            category = catalog_cache.get_category(screen.category_id)
            if not category:
                await _edit_to_text(message, "Категория не найдена",
                                    InlineKeyboardMarkup(inline_keyboard=[[
                                        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                                    ]]))
                return
            await _edit_to_text(
                message,
                f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:",
                subcategories_kb(category.subcategories),
            )

        elif screen.type == "products":
            sub = catalog_cache.get_subcategory_by_id(screen.subcategory_id)
            if not sub:
                await _edit_to_text(message, "Подкатегория не найдена",
                                    InlineKeyboardMarkup(inline_keyboard=[[
                                        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                                    ]]))
                return
            if not sub.products:
                await _edit_to_text(
                    message,
                    f"📁 <b>{sub.name}</b>\n\nТоваров нет.",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
                        InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
                    ]]),
                )
                return
            await render_product_card(message, sub.products[0], 0, len(sub.products))

        elif screen.type == "product":
            product = catalog_cache.get_product(screen.product_id)
            if not product:
                await _edit_to_text(message, "Товар не найден",
                                    InlineKeyboardMarkup(inline_keyboard=[[
                                        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                                    ]]))
                return
            sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
            products = sub.products if sub else [product]
            idx = next((i for i, p in enumerate(products) if p.id == product.id), 0)
            await render_product_card(message, product, idx, len(products))

        elif screen.type == "cart":
            from app.bot.handlers.menu import build_cart_text, build_cart_keyboard
            user_id = message.chat.id
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BASE_URL}/cart/{user_id}")
            data = response.json()
            if not data.get("items"):
                await _edit_to_text(
                    message,
                    "🛒 Ваша корзина пуста",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")
                    ]]),
                )
            else:
                await _edit_to_text(
                    message,
                    build_cart_text(data),
                    build_cart_keyboard(data),
                )


render_engine = RenderEngine()
