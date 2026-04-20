from sqlalchemy.ext.asyncio import create_async_engine
import os

DATABASE_URL = f"postgresql+asyncpg://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # поставь True только для отладки
    pool_pre_ping=True,  # полезно при работе в Docker
)