from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.keyboards.lists_menu import lists_keyboard
from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription
from bot.utils.db import get_statuses, list_users_by_status
from bot.utils.status import status_photo, status_title

router = Router()


def lists_text() -> str:
    titles = [status.get("title", code) for code, status in get_statuses().items()]
    body = "\n".join(titles)
    return f"📋 Выберите список:\n{body}" if body else "Нет доступных списков"


def format_list(status_code: str) -> str:
    users = list_users_by_status(status_code)
    title = status_title(status_code)
    if not users:
        return f"{title}:\nЗаписей нет."
    lines = "\n".join(
        [
            f"🔹 @{user.get('username')}" if user.get("username") else f"🔹 id {user.get('id')}"
            for user in users
        ]
    )
    return f"{title}:\n{lines}"


@router.callback_query(F.data == "menu_lists")
async def handle_lists_menu(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    await call.message.answer(lists_text(), reply_markup=lists_keyboard())


@router.callback_query(F.data.startswith("list_"))
async def handle_list_item(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    code = call.data.replace("list_", "")
    statuses = get_statuses()
    if code not in statuses:
        await call.message.answer("Категория не найдена.")
        return
    await call.message.answer_photo(
        photo=status_photo(code),
        caption=format_list(code),
    )


@router.message(F.text == "Списки")
async def handle_lists_text(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    await message.answer(lists_text(), reply_markup=lists_keyboard())
