from fastapi import FastAPI
from sqlalchemy import text

import app.db.init_models

from app.db.engine import engine
from app.db.base import Base
from app.db.engine import engine
from app.models import products
from app.api.routes.products import router as products_router
from app.api.routes.cart import router as cart_router

app = FastAPI()
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/db-test")
async def db_test():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            return {"db": "ok", "result": value}
    except Exception as e:
        return {"db": "error", "detail": str(e)}

@app.get("/create-tables")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return {"status": "tables created"}

app.include_router(products_router)
app.include_router(cart_router)