import httpx
from aiogram.types import InputMediaPhoto, FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.services.catalog_cache import catalog_cache
from app.bot.keyboards.catalog import (
    categories_kb,
    subcategories_kb,
    products_kb,
    product_kb,
)

BASE_URL = "http://app:8000"
BASE_MEDIA_URL = "http://app:8000/media"


class RenderEngine:

    async def render(self, screen, message):

        # ─────────────────────────────
        # CATEGORIES
        # ─────────────────────────────
        if screen.type == "categories":
            categories = catalog_cache.get_categories()
            return await message.edit_text(
                "🗂 <b>Каталог</b>\n\nВыберите категорию:",
                reply_markup=categories_kb(categories),
                parse_mode="HTML",
            )

        # ─────────────────────────────
        # SUBCATEGORIES
        # ─────────────────────────────
        if screen.type == "subcategories":
            category = catalog_cache.get_category(screen.category_id)
            if not category:
                return await message.edit_text("Категория не найдена")
            return await message.edit_text(
                f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:",
                reply_markup=subcategories_kb(category.subcategories),
                parse_mode="HTML",
            )

        # ─────────────────────────────
        # PRODUCTS LIST
        # ─────────────────────────────
        if screen.type == "products":
            sub = catalog_cache.get_subcategory_by_id(screen.subcategory_id)
            if not sub:
                return await message.edit_text("Подкатегория не найдена")
            return await message.edit_text(
                f"📦 <b>{sub.name}</b>\n\nВыберите товар:",
                reply_markup=products_kb(sub.products),
                parse_mode="HTML",
            )

        # ─────────────────────────────
        # PRODUCT DETAIL
        # ─────────────────────────────
        if screen.type == "product":
            product = catalog_cache.get_product(screen.product_id)
            if not product:
                return await message.edit_text("Товар не найден")
            sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
            products = sub.products if sub else [product]
            idx = next((i for i, p in enumerate(products) if p.id == product.id), 0)
            return await _render_product_card(message, product, idx, len(products))

        # ─────────────────────────────
        # CART
        # ─────────────────────────────
        if screen.type == "cart":
            from app.bot.handlers.menu import build_cart_text, build_cart_keyboard
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            user_id = message.chat.id
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BASE_URL}/cart/{user_id}")
            data = response.json()

            if not data.get("items"):
                return await message.edit_text(
                    "🛒 Ваша корзина пуста",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
                    ]),
                )

            return await message.edit_text(
                build_cart_text(data),
                reply_markup=build_cart_keyboard(data),
                parse_mode="HTML",
            )

async def _render_product_card(message, product, idx: int, total: int):
    sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
    products = sub.products if sub else [product]

    lines = [f"📦 <b>{product.name}</b>"]
    if getattr(product, 'discount_price', None):
        lines.append(f"💰 <s>{product.price} ₽</s> → <b>{product.discount_price} ₽</b>")
    else:
        lines.append(f"💰 <b>{product.price} ₽</b>")
    if product.description:
        lines.append(f"\n{product.description}")
    if product.characteristics:
        lines.append(f"\n📋 <i>{product.characteristics}</i>")
    text = "\n".join(lines)

    # Навигационный ряд: ← 2/5 →
    nav_row = []
    if idx > 0:
        prev = products[idx - 1]
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"open_product_{prev.id}"))
    nav_row.append(InlineKeyboardButton(text=f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nxt = products[idx + 1]
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"open_product_{nxt.id}"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        nav_row,
        [
            InlineKeyboardButton(text="➖", callback_data=f"cart_dec_{product.id}"),
            InlineKeyboardButton(text="🛒 В корзину", callback_data=f"cart_add_{product.id}"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_inc_{product.id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])

    if product.image:
        try:
            return await message.edit_media(
                media=InputMediaPhoto(media=product.image, caption=text, parse_mode="HTML"),
                reply_markup=kb,
            )
        except Exception:
            pass

    return await message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# singleton
render_engine = RenderEngine()
