from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Каталог", callback_data="menu_catalog")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="menu_cart")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="menu_orders")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="menu_question")],
    ])