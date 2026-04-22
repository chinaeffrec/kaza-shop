from aiogram import Router, F
from aiogram.types import CallbackQuery
import httpx

router = Router()
BASE_URL = "http://app:8000"


@router.callback_query(F.data.startswith("cart_add_"))
async def add_to_cart(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/cart/", json={
            "user_id": user_id,
            "product_id": product_id,
            "quantity": 1
        })

    if resp.status_code == 200:
        await callback.answer("✅ Добавлено в корзину")
    else:
        await callback.answer("Ошибка добавления в корзину", show_alert=True)
