"""
Сервис инвалидации кэша каталога в боте.
Вынесен отдельно — используется из product_service, imports_service, catalog route.
"""
import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

# Храним ссылку на активную задачу — без этого GC может её отменить до завершения
_invalidate_task: asyncio.Task | None = None


async def _do_invalidate() -> None:
    """Фактический HTTP-запрос к боту. Запускается в фоне через create_task."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post("http://bot:8001/reload-cache")
            logger.debug("Bot catalog cache invalidated")
    except Exception as e:
        logger.warning("Could not invalidate bot catalog cache: %s", e)


async def invalidate_catalog_cache() -> None:
    """Fire-and-forget: запускает инвалидацию кэша в фоне, не блокируя ответ клиенту."""
    global _invalidate_task
    _invalidate_task = asyncio.create_task(_do_invalidate())
