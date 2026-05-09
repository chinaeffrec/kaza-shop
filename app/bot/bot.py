import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers.cart import router as cart_router
from app.bot.handlers.cart_actions import router as cart_actions_router
from app.bot.handlers.catalog import router as catalog_router
from app.bot.handlers.faq import router as faq_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.start import router as start_router
from app.bot.services.catalog_cache import catalog_cache
from app.core.config import get_settings
from app.logging_setup import configure_logging

configure_logging("bot")
logger = logging.getLogger(__name__)
_cfg = get_settings()


def _make_storage():
    """RedisStorage если Redis доступен, иначе MemoryStorage с предупреждением."""
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(_cfg.redis_url)
        logger.info("FSM storage: Redis (%s)", _cfg.redis_url)
        return storage
    except Exception as e:
        from aiogram.fsm.storage.memory import MemoryStorage
        logger.warning("Redis недоступен (%s) — используется MemoryStorage. "
                       "Состояния бота будут сброшены при перезапуске.", e)
        return MemoryStorage()


async def on_startup(bot: Bot):
    await catalog_cache.load()
    logger.info("Catalog cache loaded")


async def main():
    bot = Bot(token=_cfg.bot_token)
    dp = Dispatcher(storage=_make_storage())
    dp.startup.register(on_startup)

    dp.include_router(start_router)
    dp.include_router(faq_router)
    dp.include_router(menu_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(cart_actions_router)

    from aiohttp import web

    async def handle_reload(request):
        await catalog_cache.load()
        logger.info("Cache reloaded via HTTP")
        return web.Response(text="ok")

    # Порт 8001 не публикуется на хост (см. docker-compose), доступен только
    # внутри Docker-сети — app-контейнер обращается как http://bot:8001
    http_app = web.Application()
    http_app.router.add_post("/reload-cache", handle_reload)
    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    logger.info("Cache reload server on :8001 (Docker internal network only)")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
