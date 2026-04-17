from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import httpx

router = Router()

BASE_URL = "http://app:8000"

@router.callback_query(F.data.startswith("product_"))
async def product_detail(callback: CallbackQuery):
    if not callback.data or not callback.data.startswith("product_"):
        return
    try:
        product_id = callback.data.split("_")[1]
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных")
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/products/{product_id}")
        if response.status_code != 200:
            await callback.answer("Ошибка загрузки товара")
            return

        product = response.json()
    text = (
        f"📦 {product['name']}\n\n"
        f"💰 Цена: {product['price']} ₽\n"
        f"🏷 Категория: {product['category']}\n\n"
        f"📝 Описание:\n{product.get('description') or '—'}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 В корзину",
                    callback_data=f"add_{product_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад в каталог",
                    callback_data="back_to_catalog"
                )
            ]
        ]
    )

    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()