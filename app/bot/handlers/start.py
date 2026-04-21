import httpx
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.bot.keyboards.menu import main_menu

router = Router()
BASE_URL = "http://app:8000"
DEFAULT_WELCOME = "👋 Добро пожаловать!\n\nВыберите действие:"


@router.message(Command("start"))
async def start_handler(message: Message):
    welcome_text = DEFAULT_WELCOME
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{BASE_URL}/settings/")
            if r.status_code == 200:
                cfg = r.json()
                welcome_text = cfg.get("welcome_message") or DEFAULT_WELCOME
    except Exception:
        pass

    await message.answer(welcome_text, reply_markup=main_menu())