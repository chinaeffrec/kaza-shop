"""
Миграция: добавляет недостающие колонки в существующие таблицы.
Запуск: docker exec kaza_shop-app-1 python -m app.db.migrate
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
    # products
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_file_id VARCHAR(512)",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS discount_price INTEGER",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INTEGER DEFAULT 0",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
    # Если characteristics был JSON — меняем на TEXT
    "ALTER TABLE products ALTER COLUMN characteristics TYPE TEXT USING characteristics::TEXT",
    # categories/subcategories — убираем slug если есть
    "ALTER TABLE categories DROP COLUMN IF EXISTS slug",
    "ALTER TABLE subcategories DROP COLUMN IF EXISTS slug",
    # orders
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS comment TEXT",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_address TEXT",
    # shop_settings
    "ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS welcome_message TEXT",
    "ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS seller_contact VARCHAR(256)",
    "ALTER TABLE shop_settings ADD COLUMN IF NOT EXISTS admin_contact VARCHAR(256)",
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
