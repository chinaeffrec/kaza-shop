from aiogram import Router, F
from aiogram.types import CallbackQuery
import httpx

router = Router()

BASE_URL = "http://app:8000"

@router.callback_query(F.data.startswith("add_"))

async def add_to_cart(callback: CallbackQuery):
    print("🔥 CLICK:", callback.data)
    product_id = callback.data.split("_")[1]
    user_id = callback.from_user.id
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/cart/",
            json={
                "user_id": user_id,
                "product_id": int(product_id),
                "quantity": 1
            }
        )
    print("STATUS:", response.status_code)
    await callback.answer("Добавлено 🛒")