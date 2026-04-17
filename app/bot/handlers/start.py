from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from app.bot.services.products_api import fetch_products

router = Router()

@router.message(Command('start'))
async def start_handler(message: Message):
    products = await fetch_products()

    if not products:
        await message.answer("Products not found")
        return

    for product in products:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Подробнее",
                        callback_data=f"product_{product['id']}",
                    )
                ]
            ]
        )

        text = (
            f"{product['name']}\n"
            f"Цена: {product['price']} ₽\n"
            f"Категория: {product['category']}\n"
        )
    await message.answer(
        text, reply_markup=keyboard
    )