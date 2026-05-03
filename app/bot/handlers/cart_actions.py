import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

router = Router()
BASE_URL = "http://app:8000"

async def refresh_cart(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/cart/{user_id}")
    data = response.json()

    from app.bot.handlers.menu import build_cart_keyboard, build_cart_text
    if not data.get("items"):
        await callback.message.edit_text(
            "Ваша корзина пуста",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")]
            ])
        )
        return
    await callback.message.edit_text(
        build_cart_text(data),
        reply_markup=build_cart_keyboard(data),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("inc_"))
async def inc(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/cart/inc", json={
            "user_id": callback.from_user.id,
            "product_id": product_id
        })

    await refresh_cart(callback)
    await callback.answer()

@router.callback_query(F.data.startswith("dec_"))
async def dec(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/cart/dec", json={
            "user_id": callback.from_user.id,
            "product_id": product_id
        })

    await refresh_cart(callback)
    await callback.answer()

@router.callback_query(F.data.startswith("rm_"))
async def remove(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/cart/remove", json={
            "user_id": callback.from_user.id,
            "product_id": product_id
        })

    await refresh_cart(callback)
    await callback.answer()
