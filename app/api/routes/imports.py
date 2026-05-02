from io import BytesIO
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from app.db.session import get_session
from app.models.category import Category
from app.models.subcategory import SubCategory
from app.models.product import Product

router = APIRouter(prefix="/import", tags=["import"])

# Ожидаемые колонки xlsx:
# category, subcategory, name, price, discount_price, description, characteristics, is_active


async def _get_or_create_category(session: AsyncSession, name: str) -> Category:
    name = name.strip()
    res = await session.execute(select(Category).where(Category.name == name))
    cat = res.scalar_one_or_none()
    if not cat:
        cat = Category(name=name)
        session.add(cat)
        await session.flush()
    return cat


async def _get_or_create_subcategory(session: AsyncSession, category_id: int, name: str) -> SubCategory:
    name = name.strip()
    res = await session.execute(
        select(SubCategory).where(SubCategory.name == name, SubCategory.category_id == category_id)
    )
    sub = res.scalar_one_or_none()
    if not sub:
        sub = SubCategory(name=name, category_id=category_id)
        session.add(sub)
        await session.flush()
    return sub


@router.post("/products")
async def import_products(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx or .xls files are allowed")

    try:
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Error reading Excel file: {e}")

    # Проверяем обязательные колонки
    required = {"category", "subcategory", "name", "price"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")

    created = updated = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            name = str(row["name"]).strip()
            if not name or name == "nan":
                continue

            category = await _get_or_create_category(session, str(row["category"]))
            subcategory = await _get_or_create_subcategory(session, category.id, str(row["subcategory"]))

            price = int(float(row["price"]))
            discount_price = None
            if "discount_price" in df.columns and not pd.isna(row.get("discount_price")):
                try:
                    discount_price = int(float(row["discount_price"]))
                except Exception:
                    pass

            description = None
            if "description" in df.columns and not pd.isna(row.get("description")):
                description = str(row["description"]).strip() or None

            characteristics = None
            if "characteristics" in df.columns and not pd.isna(row.get("characteristics")):
                characteristics = str(row["characteristics"]).strip() or None

            is_active = True
            if "is_active" in df.columns and not pd.isna(row.get("is_active")):
                val = row["is_active"]
                if isinstance(val, bool):
                    is_active = val
                elif str(val).strip().lower() in ("false", "0", "нет", "no"):
                    is_active = False

            stock = 0
            if "stock" in df.columns and not pd.isna(row.get("stock")):
                try:
                    stock = int(float(row["stock"]))
                except Exception:
                    stock = 0

            # Ищем по имени + подкатегория
            res = await session.execute(
                select(Product).where(Product.name == name, Product.subcategory_id == subcategory.id)
            )
            existing = res.scalar_one_or_none()

            if existing:
                existing.price = price
                existing.discount_price = discount_price
                existing.description = description
                existing.characteristics = characteristics
                existing.is_active = is_active
                existing.stock = stock
                updated += 1
            else:
                session.add(Product(
                    subcategory_id=subcategory.id,
                    name=name,
                    price=price,
                    discount_price=discount_price,
                    description=description,
                    characteristics=characteristics,
                    stock=stock,
                    is_active=is_active,
                ))
                created += 1

            await session.commit()

        except Exception as e:
            await session.rollback()
            errors.append(f"Row {idx} ({row.get('name', '?')}): {e}")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post("http://bot:8001/reload-cache")
    except Exception:
        pass

    return {"status": "ok", "created": created, "updated": updated, "errors": errors}
