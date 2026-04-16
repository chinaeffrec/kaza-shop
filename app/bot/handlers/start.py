from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.bot.services.products_api import fetch_products

router = Router()

@router.message(Command('start'))
async def start_handler(message: Message):
    products = await fetch_products()

    if not products:
        await message.answer("Products not found")
        return

    text = "Catalog:\n\n"
    for product in products[:10]:
        text += (
            f"ID: {product['id']}\n"
            f"Name: {product['name']}\n"
            f"Price: {product['price']}\n"
            f"---\n"
        )
    await message.answer(
        text
    )