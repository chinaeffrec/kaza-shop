from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.bot.services.navigation import navigation
from app.bot.services.render_engine import render_engine, render_product_card
from app.bot.services.catalog_cache import catalog_cache
from app.bot.states.screen import Screen

router = Router()


@router.callback_query(F.data.startswith("open_"))
async def open_handler(callback: CallbackQuery):
    """
    open_category_{id}  — переход в подкатегории
    open_sub_{id}       — переход в список товаров
    open_product_{id}   — карточка товара + стрелки навигации
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    entity = parts[1]        # category | sub | product
    entity_id = int(parts[-1])

    if entity == "category":
        screen = Screen(type="subcategories", category_id=entity_id)
        navigation.push(user_id, screen)
        await render_engine.render(screen, callback.message)

    elif entity == "sub":
        screen = Screen(type="products", subcategory_id=entity_id)
        navigation.push(user_id, screen)
        await render_engine.render(screen, callback.message)

    elif entity == "product":
        product = catalog_cache.get_product(entity_id)
        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            return
        sub = catalog_cache.get_subcategory_by_id(product.subcategory_id)
        products = sub.products if sub else [product]
        idx = next((i for i, p in enumerate(products) if p.id == entity_id), 0)
        screen = Screen(type="product", product_id=entity_id)
        navigation.push(user_id, screen)
        await render_product_card(callback.message, product, idx, len(products))

    await callback.answer()


@router.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    user_id = callback.from_user.id
    navigation.pop(user_id)
    screen = navigation.peek(user_id)
    if not screen:
        screen = Screen(type="categories")
        navigation.push(user_id, screen)
    await render_engine.render(screen, callback.message)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
