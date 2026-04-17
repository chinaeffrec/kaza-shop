from aiogram import Router
from aiogram.types import Message
import httpx

router = Router()
BASE_URL = "http://app:8000"

@router.message()
async def show_cart(message: Message):
    if message.text != "/cart":
        return
    user_id = message.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/cart/{user_id}")

        print("STATUS:", response.status_code)
        print("TEXT:", response.text)

        data = response.json()

    if not data["items"]:
        await message.answer("Корзина пуста")
        return
    text = "Ваша корзина:\n\n"
    for item in data["items"]:
        text += (
            f"• {item['name']} ×{item['quantity']} — {item['sum']}₽\n"
        )
    text += f"\nИтого: {data['total']} ₽"

    await message.answer(text)