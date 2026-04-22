from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from pathlib import Path

import app.models
import app.db.init_models

from app.db.engine import engine
from app.db.base import Base

from app.api.routes.products import router as products_router
from app.api.routes.cart import router as cart_router
from app.api.routes.imports import router as import_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.orders import router as orders_router
from app.api.routes.settings import router as settings_router, faq_router
from app.api.routes.stats import router as stats_router
from app.api.routes.auth import router as auth_router

app = FastAPI(title="Kaza Shop API", version="0.4.0")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[app] Tables created / verified")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Медиа лежат в /app/media (volume)
MEDIA_DIR = Path("/app/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/db-test")
async def db_test():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return {"db": "ok", "result": result.scalar()}
    except Exception as e:
        return {"db": "error", "detail": str(e)}


app.include_router(auth_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(import_router)
app.include_router(catalog_router)
app.include_router(orders_router)
app.include_router(settings_router)
app.include_router(faq_router)
app.include_router(stats_router)
