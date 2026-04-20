from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.bot.services.navigation import navigation
from app.bot.services import render_engine
from app.bot.states.screen import Screen

router = Router()


# =========================
# OPEN HANDLER
# =========================
@router.callback_query(F.data.startswith("open_"))
async def open_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    parts = callback.data.split("_")
    entity = parts[1]

    if entity == "category":
        screen = Screen(
            type="subcategories",
            category_id=int(parts[2])
        )

    elif entity == "sub":
        screen = Screen(
            type="products",
            subcategory_id=int(parts[2])
        )

    elif entity == "product":
        screen = Screen(
            type="product",
            product_id=int(parts[2])
        )

    navigation.push(user_id, screen)

    await render_engine.render(screen, callback.message)
    await callback.answer()


# =========================
# BACK
# =========================
@router.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    user_id = callback.from_user.id

    navigation.pop(user_id)
    screen = navigation.peek(user_id)

    if not screen:
        screen = Screen(type="categories")

    await render_engine.render(screen, callback.message)
    await callback.answer()


# =========================
# MENU BACK
# =========================
@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery):
    user_id = callback.from_user.id

    navigation.reset(user_id)

    screen = Screen(type="categories")
    navigation.push(user_id, screen)

    await render_engine.render(screen, callback.message)
    await callback.answer()