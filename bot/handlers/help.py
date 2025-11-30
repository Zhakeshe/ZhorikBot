from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription
from bot.utils.db import get_statuses

router = Router()

HELP_TEXT = (
    "📌 Основные команды:\n"
    "/search — 🔍 Найти пользователя\n"
    "/me — 📊 Проверить свой статус\n"
    "/help — ❓ Показать это меню\n"
    "/info — ⚙️ Показать меню статусов\n\n"
    "🔍 Способы поиска:\n"
    "• По ID — id123456789\n"
    "• По нику — @username\n\n"
    "⸻\n\n"
    "✨ Инлайн-режим:\n"
    "Введите @ZhorikBaseRobot в любом чате и:\n"
    "• @username — поиск по нику\n"
    "• id123456789 — поиск по ID\n\n"
    "✅ В группах:\n"
    "• /check username\n"
    "• /check id123456789"
)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    await message.answer(HELP_TEXT)


@router.message(Command("info"))
async def handle_info(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    statuses = get_statuses()
    lines = [f"{data.get('title', code)} — {data.get('description', '')}" for code, data in statuses.items()]
    await message.answer("Доступные статусы:\n" + "\n".join(lines))


@router.callback_query(F.data == "menu_help")
async def handle_menu_help(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    await call.message.answer(HELP_TEXT)
