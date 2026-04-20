import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.bot.states.contact import ContactState
from app.bot.keyboards.menu import main_menu

router = Router()

SELLER_CHAT_ID = os.getenv("SELLER_CHAT_ID")  # задать в .env


@router.callback_query(F.data == "menu_question")
async def start_contact(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ContactState.waiting_for_message)
    await callback.message.edit_text(
        "💬 <b>Связь с продавцом</b>\n\n"
        "Напишите ваш вопрос — и мы передадим его продавцу.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_contact")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_contact")
async def cancel_contact(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Добро пожаловать!\n\nВыберите действие:",
        reply_markup=main_menu(),
    )
    await callback.answer()


@router.message(ContactState.waiting_for_message)
async def receive_question(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    user_info = f"@{user.username}" if user.username else f"id:{user.id}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    # Пересылаем продавцу
    if SELLER_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=int(SELLER_CHAT_ID),
                text=(
                    f"📩 <b>Вопрос от покупателя</b>\n\n"
                    f"👤 {full_name} ({user_info})\n\n"
                    f"💬 {message.text}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"[contact] Ошибка отправки продавцу: {e}")

    await state.clear()
    await message.answer(
        "✅ Ваш вопрос отправлен продавцу!\n\nМы ответим вам в ближайшее время.",
        reply_markup=main_menu(),
    )
