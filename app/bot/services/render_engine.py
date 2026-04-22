import httpx
from aiogram.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.services.catalog_cache import catalog_cache
from app.bot.keyboards.catalog import categories_kb, subcategories_kb

BASE_URL = "http://app:8000"
# Публичный URL медиа — используется для отправки фото через URL
MEDIA_BASE = "http://app:8000/media"


def _fmt_price(price: int | float) -> str:
    if isinstance(price, float) and price != int(price):
        return f"{price:,.2f} ₽".replace(",", " ")
    return f"{int(price):,} ₽".replace(",", " ")


async def _render_product_card(message, product, idx: int, total: int):
    sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
    products = sub.products if sub else [product]

    lines = [f"📦 <b>{product.name}</b>"]
    if getattr(product, "discount_price", None):
        lines.append(
            f"💰 <s>{_fmt_price(product.price)}</s> → <b>{_fmt_price(product.discount_price)}</b>"
        )
    else:
        lines.append(f"💰 <b>{_fmt_price(product.price)}</b>")
    if product.description:
        lines.append(f"\n{product.description}")
    if product.characteristics:
        lines.append(f"\n📋 <i>{product.characteristics}</i>")
    text = "\n".join(lines)

    # Навигация ← N/M →
    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"open_product_{products[idx-1].id}"))
    nav_row.append(InlineKeyboardButton(text=f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"open_product_{products[idx+1].id}"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        nav_row,
        [
            InlineKeyboardButton(text="➖", callback_data=f"cart_dec_{product.id}"),
            InlineKeyboardButton(text="🛒 В корзину", callback_data=f"cart_add_{product.id}"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_inc_{product.id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])

    # Фото: image — это имя файла (image_file_id из БД)
    # Отправляем через URL, не через Telegram file_id
    if product.image:
        image_url = f"{MEDIA_BASE}/{product.image}"
        try:
            return await message.edit_media(
                media=InputMediaPhoto(media=image_url, caption=text, parse_mode="HTML"),
                reply_markup=kb,
            )
        except Exception as e:
            print(f"[render] Image send failed ({product.image}): {e}")
            # Fallback: текстовый режим
            pass

    return await message.edit_text(text, reply_markup=kb, parse_mode="HTML")


class RenderEngine:

    async def render(self, screen, message):

        if screen.type == "categories":
            categories = catalog_cache.get_categories()
            return await message.edit_text(
                "🗂 <b>Каталог</b>\n\nВыберите категорию:",
                reply_markup=categories_kb(categories),
                parse_mode="HTML",
            )

        if screen.type == "subcategories":
            category = catalog_cache.get_category(screen.category_id)
            if not category:
                return await message.edit_text("Категория не найдена")
            return await message.edit_text(
                f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:",
                reply_markup=subcategories_kb(category.subcategories),
                parse_mode="HTML",
            )

        if screen.type == "products":
            sub = catalog_cache.get_subcategory_by_id(screen.subcategory_id)
            if not sub:
                return await message.edit_text("Подкатегория не найдена")
            if not sub.products:
                return await message.edit_text(
                    f"📁 <b>{sub.name}</b>\n\nТоваров нет.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
                    ]),
                    parse_mode="HTML",
                )
            # Открываем первый товар с навигацией
            return await _render_product_card(message, sub.products[0], 0, len(sub.products))

        if screen.type == "product":
            product = catalog_cache.get_product(screen.product_id)
            if not product:
                return await message.edit_text("Товар не найден")
            sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
            products = sub.products if sub else [product]
            idx = next((i for i, p in enumerate(products) if p.id == product.id), 0)
            return await _render_product_card(message, product, idx, len(products))

        if screen.type == "cart":
            from app.bot.handlers.menu import build_cart_text, build_cart_keyboard
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


render_engine = RenderEngine()
