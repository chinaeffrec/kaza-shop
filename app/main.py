import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

import app.models
from app.api.routes.auth import router as auth_router
from app.api.routes.cart import router as cart_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as import_router
from app.api.routes.orders import router as orders_router
from app.api.routes.products import router as products_router
from app.api.routes.settings import faq_router, router as settings_router
from app.api.routes.stats import router as stats_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.db.base import Base
from app.db.engine import engine
from app.logging_setup import configure_logging

configure_logging("app")
logger = logging.getLogger(__name__)
cfg = get_settings()

# Гарантируем корректный MIME-тип для WebP на любом Linux-образе.
# На minimal Docker images системный /etc/mime.types может не включать WebP,
# тогда StaticFiles отдаёт application/octet-stream + nosniff = браузер не
# отображает изображение. Явная регистрация решает это раз и навсегда.
mimetypes.add_type("image/webp", ".webp")

app = FastAPI(
    title="Kaza Shop API",
    version="1.0.0",
    docs_url="/docs" if not cfg.is_production else None,
    redoc_url="/redoc" if not cfg.is_production else None,
    openapi_url="/openapi.json" if not cfg.is_production else None,
)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Функциональный индекс для поиска без full scan.
        # translate() + lower() = locale-independent (работает с C-локалью PostgreSQL).
        await conn.execute(text("DROP INDEX IF EXISTS ix_products_name_lower"))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_products_name_ci ON products "
            "(lower(translate(name,"
            " 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ',"
            " 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя')))"
        ))

        # Колонки добавленные после первого релиза — ADD COLUMN IF NOT EXISTS
        # безопасен при повторных запусках и на свежих установках.
        await conn.execute(text("""
            ALTER TABLE shop_settings
                ADD COLUMN IF NOT EXISTS stamp_filename       VARCHAR,
                ADD COLUMN IF NOT EXISTS payment_qr_filename  VARCHAR,
                ADD COLUMN IF NOT EXISTS payment_qr_comment   VARCHAR,
                ADD COLUMN IF NOT EXISTS legal_name           VARCHAR
        """))

    logger.info("DB tables verified. Kaza Shop started.")


# ── Middleware ─────────────────────────────────────────────────────────────────
# "app" и "bot" — имена контейнеров внутри Docker-сети
allowed_hosts = ["localhost", "127.0.0.1", "app", "bot"]
if cfg.domain and cfg.domain != "localhost":
    allowed_hosts.append(cfg.domain)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Static ─────────────────────────────────────────────────────────────────────
for d in (Path("/app/media"), Path("/app/data"), Path("/app/logs")):
    d.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory="/app/media"), name="media")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(import_router)
app.include_router(catalog_router)
app.include_router(orders_router)
app.include_router(settings_router)
app.include_router(faq_router)
app.include_router(stats_router)
app.include_router(users_router)
