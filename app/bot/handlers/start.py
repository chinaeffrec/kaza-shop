from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from app.bot.keyboards.menu import main_menu

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 Добро пожаловать в Kaza Shop!\n\nВыберите действие в меню ниже:",
        reply_markup=main_menu()
    )