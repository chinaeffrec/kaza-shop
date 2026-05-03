import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()
BASE_URL = "http://app:8000"


@router.callback_query(F.data.startswith("cart_add_"))
async def add_to_cart(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{BASE_URL}/cart/",
                json={"user_id": user_id, "product_id": product_id, "quantity": 1},
            )
        if resp.status_code == 200:
            await callback.answer("✅ Добавлено в корзину")
        else:
            await callback.answer(f"Ошибка сервера: {resp.status_code}", show_alert=True)
    except httpx.RequestError as e:
        await callback.answer(f"Нет связи с сервером", show_alert=True)
