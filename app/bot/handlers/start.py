import httpx
import time
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.bot.keyboards.menu import main_menu
from app.bot.services.bot_messages import track

router = Router()
BASE_URL = "http://app:8000"
DEFAULT_WELCOME = "👋 Добро пожаловать!\n\nВыберите действие:"

# Дедупликация /start на Android (клиент может слать скрытый + явный)
_last_start: dict[int, float] = {}


@router.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    now = time.time()

    # Игнорируем дубли в течение 3 секунд
    if user_id in _last_start and (now - _last_start[user_id]) < 3:
        # Удаляем дубликат сообщения (баг клиента Android)
        try:
            await message.delete()
        except Exception:
            pass
        return
    _last_start[user_id] = now

    # Регистрируем пользователя
    user = message.from_user
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(f"{BASE_URL}/users/register", json={
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            })
    except Exception:
        pass

    welcome_text = DEFAULT_WELCOME
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{BASE_URL}/settings/")
            if r.status_code == 200:
                welcome_text = r.json().get("welcome_message") or DEFAULT_WELCOME
    except Exception:
        pass

    sent = await message.answer(welcome_text, reply_markup=main_menu())
    track(message.chat.id, sent.message_id)