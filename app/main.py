from fastapi import FastAPI
from sqlalchemy import text

from app.db.engine import engine

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