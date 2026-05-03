import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

router = Router()
BASE_URL = "http://app:8000"


@router.callback_query(F.data == "menu_faq")
async def open_faq(callback: CallbackQuery):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/faq/")
    items = [i for i in resp.json() if i.get("is_active")]

    if not items:
        await callback.message.edit_text(
            "❓ FAQ пока пуст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
            ])
        )
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=item["question"], callback_data=f"faq_{item['id']}")]
        for item in items
    ] + [[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]])

    await callback.message.edit_text("❓ <b>Часто задаваемые вопросы</b>", reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def show_faq_answer(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/faq/")
    items = {i["id"]: i for i in resp.json()}
    item = items.get(item_id)

    if not item:
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"❓ <b>{item['question']}</b>\n\n{item['answer']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К вопросам", callback_data="menu_faq")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")],
        ]),
        parse_mode="HTML"
    )
    await callback.answer()
