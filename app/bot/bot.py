import asyncio
from aiogram import Bot, Dispatcher

from app.bot.handlers.start import router as start_router
from app.bot.handlers.product import router as product_router
from app.bot.handlers.cart import router as cart_router
from app.bot.handlers.cart_view import router as cart_view_router

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(product_router)
    dp.include_router(cart_router)
    dp.include_router(cart_view_router)

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())