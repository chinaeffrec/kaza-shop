"""
Миграция: приводит существующие таблицы к актуальной схеме.
Запуск (один раз после обновления кода):
  docker exec kaza_shop-app-1 python -m app.db.migrate
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

MIGRATIONS = [
    # products — убираем slug если есть, добавляем нужные поля
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_file_id VARCHAR(512)",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS discount_price INTEGER",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INTEGER DEFAULT 0",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
    # categories — убираем slug если он там есть (через DROP COLUMN IF EXISTS)
    "ALTER TABLE categories DROP COLUMN IF EXISTS slug",
    # subcategories — убираем slug
    "ALTER TABLE subcategories DROP COLUMN IF EXISTS slug",
    # orders
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS comment TEXT",
    # новые таблицы создаются через create_all при старте, миграция только для колонок
]

async def run():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for sql in MIGRATIONS:
            try:
                await conn.execute(text(sql))
                print(f"  OK  {sql[:80]}")
            except Exception as e:
                print(f" SKIP {sql[:80]}\n      → {e}")
    await engine.dispose()
    print("\n✅ Migration complete")

if __name__ == "__main__":
    asyncio.run(run())
