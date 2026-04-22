import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.start import router as start_router
from app.bot.handlers.faq import router as faq_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.catalog import router as catalog_router
from app.bot.handlers.cart import router as cart_router
from app.bot.handlers.cart_actions import router as cart_actions_router

from app.bot.services.catalog_cache import catalog_cache

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def on_startup(bot: Bot):
    await catalog_cache.load()
    print("[bot] Catalog cache loaded")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.startup.register(on_startup)

    # Порядок важен: menu содержит FSM-хендлеры checkout
    dp.include_router(start_router)
    dp.include_router(faq_router)
    dp.include_router(menu_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(cart_actions_router)

    # HTTP-сервер для сброса кэша
    from aiohttp import web

    async def handle_reload(request):
        await catalog_cache.load()
        print("[bot] Cache reloaded via HTTP")
        return web.Response(text="ok")

    http_app = web.Application()
    http_app.router.add_post("/reload-cache", handle_reload)
    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    print("[bot] Cache reload server on :8001")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
