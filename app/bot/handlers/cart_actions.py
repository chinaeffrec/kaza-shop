import logging

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
router = Router()
BASE_URL = "http://app:8000"
_TIMEOUT = httpx.Timeout(10.0)


async def refresh_cart(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/cart/{user_id}")
        data = response.json()
    except Exception as e:
        logger.warning("refresh_cart failed for user %s: %s", user_id, e)
        await callback.answer("Ошибка соединения, попробуйте позже", show_alert=True)
        return

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
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(f"{BASE_URL}/cart/inc", json={
                "user_id": callback.from_user.id,
                "product_id": product_id
            })
    except Exception as e:
        logger.warning("cart inc failed: %s", e)
        await callback.answer("Ошибка, попробуйте позже", show_alert=True)
        return

    await refresh_cart(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("dec_"))
async def dec(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(f"{BASE_URL}/cart/dec", json={
                "user_id": callback.from_user.id,
                "product_id": product_id
            })
    except Exception as e:
        logger.warning("cart dec failed: %s", e)
        await callback.answer("Ошибка, попробуйте позже", show_alert=True)
        return

    await refresh_cart(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("rm_"))
async def remove(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(f"{BASE_URL}/cart/remove", json={
                "user_id": callback.from_user.id,
                "product_id": product_id
            })
    except Exception as e:
        logger.warning("cart remove failed: %s", e)
        await callback.answer("Ошибка, попробуйте позже", show_alert=True)
        return

    await refresh_cart(callback)
    await callback.answer()
