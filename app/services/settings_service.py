"""
Сервис настроек магазина.

Кэш намеренно убран: кэширование SQLAlchemy ORM-объектов между сессиями
приводит к detached instance - объект не отслеживается текущей сессией,
и изменения через setattr + session.commit() не сохраняются в БД.
Таблица shop_settings содержит 1 строку - SELECT стоит микросекунды.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import ShopSettings

logger = logging.getLogger(__name__)


async def get_shop_settings(session: AsyncSession) -> ShopSettings:
    """Загружает настройки из БД в текущую сессию - объект гарантированно tracked."""
    res = await session.execute(select(ShopSettings).where(ShopSettings.id == 1))
    s = res.scalar_one_or_none()
    if not s:
        s = ShopSettings(id=1)
        session.add(s)
        await session.flush()
        await session.commit()
    return s


def invalidate_settings_cache() -> None:
    """Оставлен для совместимости вызовов - кэша больше нет."""
    pass
