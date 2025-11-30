from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription
from bot.utils.db import get_user
from bot.utils.status import render_profile, status_photo

router = Router()


@router.message(Command("me"))
async def handle_me(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    user = get_user(str(message.from_user.id))
    if not user:
        user = {
            "id": message.from_user.id,
            "username": message.from_user.username,
            "status": "unknown",
            "proof": "",
            "comment": "",
        }
    await message.answer_photo(
        photo=status_photo(user.get("status", "unknown")),
        caption=render_profile(user),
    )


@router.callback_query(F.data == "menu_profile")
async def handle_menu_profile(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    user = get_user(str(call.from_user.id))
    if not user:
        user = {
            "id": call.from_user.id,
            "username": call.from_user.username,
            "status": "unknown",
            "proof": "",
            "comment": "",
        }
    await call.message.answer_photo(
        photo=status_photo(user.get("status", "unknown")),
        caption=render_profile(user),
    )
