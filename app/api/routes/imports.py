from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import os
from pathlib import Path

from app.db.session import get_session
from app.models.category import Category
from app.models.subcategory import SubCategory
from app.models.product import Product

router = APIRouter(prefix="/import", tags=["import"])


async def get_or_create_category(session: AsyncSession, name: str):
    result = await session.execute(select(Category).where(Category.name == name))
    category = result.scalar_one_or_none()
    if category:
        return category

    category = Category(name=name, slug=name.lower().replace(" ", "-"))
    session.add(category)
    await session.flush()
    return category


async def get_or_create_subcategory(session: AsyncSession, category_id: int, name: str):
    result = await session.execute(
        select(SubCategory).where(
            SubCategory.name == name,
            SubCategory.category_id == category_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub:
        return sub

    sub = SubCategory(
        name=name,
        slug=name.lower().replace(" ", "-"),
        category_id=category_id
    )
    session.add(sub)
    await session.flush()
    return sub


@router.post("/products")
async def import_products(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Файл должен быть .xlsx")

    df = pd.read_excel(file.file, engine="openpyxl")

    created = 0
    for _, row in df.iterrows():
        try:
            category = await get_or_create_category(session, str(row["category"]))
            subcategory = await get_or_create_subcategory(
                session, category.id, str(row["subcategory"])
            )

            product = Product(
                subcategory_id=subcategory.id,
                name=str(row["name"]),
                slug=str(row["name"]).lower().replace(" ", "-"),
                price=int(row["price"]),
                description=str(row.get("description")) if pd.notna(row.get("description")) else None,
                characteristics=None,  # можно расширить позже
                images=None,
                stock=int(row.get("stock", 0)),
                is_active=bool(row.get("is_active", True))
            )
            session.add(product)
            created += 1
        except Exception as e:
            print(f"Ошибка при импорте строки: {e}")

    await session.commit()
    return {"status": "ok", "created": created, "message": f"Создано {created} товаров"}