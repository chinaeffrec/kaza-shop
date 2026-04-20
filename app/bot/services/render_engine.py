import httpx
from aiogram.types import InputMediaPhoto, FSInputFile

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

            lines = [f"📦 <b>{product.name}</b>", f"💰 <b>{product.price} ₽</b>"]
            if product.description:
                lines.append(f"\n{product.description}")
            if product.characteristics:
                lines.append(f"\n📋 <i>{product.characteristics}</i>")
            text = "\n".join(lines)

            kb = product_kb(product.id)

            # Если есть сохранённый Telegram file_id — используем его
            if product.image:
                try:
                    return await message.edit_media(
                        media=InputMediaPhoto(
                            media=product.image,
                            caption=text,
                            parse_mode="HTML",
                        ),
                        reply_markup=kb,
                    )
                except Exception:
                    pass  # file_id устарел — покажем текст

            # Нет фото — текстовый режим
            return await message.edit_text(
                text,
                reply_markup=kb,
                parse_mode="HTML",
            )

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


# singleton
render_engine = RenderEngine()
