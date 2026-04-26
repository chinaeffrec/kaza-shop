import logging
import httpx
from pathlib import Path
from aiogram.types import (
    InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, Message,
    BufferedInputFile
)

from app.bot.services.catalog_cache import catalog_cache
from app.bot.keyboards.catalog import categories_kb, subcategories_kb

logger = logging.getLogger(__name__)

# Бот и app оба монтируют ./media:/app/media — читаем файлы напрямую
MEDIA_DIR = Path("/app/media")


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
    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"open_product_{products[idx-1].id}"))
    nav_row.append(InlineKeyboardButton(text=f"{idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"open_product_{products[idx+1].id}"))

    return InlineKeyboardMarkup(inline_keyboard=[
        nav_row,
        [InlineKeyboardButton(text="🛒 В корзину", callback_data=f"cart_add_{product.id}")],
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
    if product.characteristics:
        lines.append(f"\n📋 {product.characteristics}")
    if product.description:
        lines.append(f"\n{product.description}")
    return "\n".join(lines)


async def render_product_card(message: Message, product, idx: int, total: int):
    sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
    products = sub.products if sub else [product]
    kb = _product_kb(product, idx, total, products)
    caption = _product_caption(product)

    # Собираем URL'ы фото
    image_urls = []
    if getattr(product, "image_url", None):
        image_urls.append(product.image_url)
    if getattr(product, "image_url_2", None):
        image_urls.append(product.image_url_2)
    if getattr(product, "image_url_3", None):
        image_urls.append(product.image_url_3)

    if not image_urls:
        await _safe_edit_text(message, caption, kb)
        return

    # Скачиваем фото через HTTP
    photos = []
    async with httpx.AsyncClient(timeout=10) as client:
        for url in image_urls:
            try:
                resp = await client.get(f"http://app:8000{url}")
                if resp.status_code == 200:
                    filename = url.split("/")[-1]
                    photos.append((filename, resp.content))
            except Exception as e:
                logger.warning("Failed to download photo %s: %s", url, e)

    if not photos:
        await _safe_edit_text(message, caption, kb)
        return

    try:
        if len(photos) == 1:
            filename, content = photos[0]
            photo = BufferedInputFile(content, filename=filename)
            try:
                await message.delete()
            except Exception:
                pass
            await message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
        else:
            media = []
            for i, (filename, content) in enumerate(photos):
                photo = BufferedInputFile(content, filename=filename)
                if i == 0:
                    media.append(InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=photo))
            try:
                await message.delete()
            except Exception:
                pass
            await message.answer_media_group(media=media)
            await message.answer("↑ Фото товара", reply_markup=kb)
    except Exception as e:
        logger.warning("Photo send error for product %s: %s", product.id, e)
        await _safe_edit_text(message, caption, kb)

async def _safe_edit_text(message: Message, text: str, kb: InlineKeyboardMarkup):
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


class RenderEngine:
    async def render(self, screen, message: Message):

        if screen.type == "categories":
            categories = catalog_cache.get_categories()
            await message.edit_text(
                "🗂 <b>Каталог</b>\n\nВыберите категорию:",
                reply_markup=categories_kb(categories),
                parse_mode="HTML",
            )

        elif screen.type == "subcategories":
            category = catalog_cache.get_category(screen.category_id)
            if not category:
                await message.edit_text(
                    "Категория не найдена",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                    ]]),
                )
                return
            await message.edit_text(
                f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:",
                reply_markup=subcategories_kb(category.subcategories),
                parse_mode="HTML",
            )

        elif screen.type in ("products", "product"):
            if screen.type == "products":
                sub = catalog_cache.get_subcategory_by_id(screen.subcategory_id)
                if not sub or not sub.products:
                    name = getattr(sub, "name", "Подкатегория") if sub else "Подкатегория"
                    await message.edit_text(
                        f"📁 <b>{name}</b>\n\nТоваров нет.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                        ]]),
                        parse_mode="HTML",
                    )
                    return
                product = sub.products[0]
                idx = 0
                total = len(sub.products)
            else:
                product = catalog_cache.get_product(screen.product_id)
                if not product:
                    await message.edit_text(
                        "Товар не найден",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                        ]]),
                    )
                    return
                sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
                products_list = sub.products if sub else [product]
                idx = next((i for i, p in enumerate(products_list) if p.id == product.id), 0)
                total = len(products_list)

            await render_product_card(message, product, idx, total)

        elif screen.type == "cart":
            from app.bot.handlers.menu import build_cart_text, build_cart_keyboard
            user_id = message.chat.id
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://app:8000/cart/{user_id}")
            data = response.json()
            if not data.get("items"):
                await _safe_edit_text(
                    message,
                    "🛒 Ваша корзина пуста",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")
                    ]]),
                )
            else:
                await _safe_edit_text(message, build_cart_text(data), build_cart_keyboard(data))


render_engine = RenderEngine()
