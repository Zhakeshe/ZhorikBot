from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription
from bot.utils.status import FOOTER

PHOTO_START = "https://i.imgur.com/4N0JrFj.png"

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    subscribed, missing = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    description = (
        "🤖 ZhorikBase — анти-скам база по пользователям.\n"
        "• Проверяйте статусы участников\n"
        "• Управляйте категориями и модераторами\n"
        "• Логируйте каждое изменение\n\n"
        f"{FOOTER}"
    )
    await message.answer_photo(
        photo=PHOTO_START,
        caption=description,
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(lambda c: c.data == "check_subs")
async def handle_check_subs(call: CallbackQuery) -> None:
    subscribed, missing = await ensure_subscription(call.bot, call.from_user)
    if subscribed:
        await call.message.answer("Спасибо! Подписка подтверждена.", reply_markup=main_menu_keyboard())
    else:
        await call.message.answer(
            "Подписка не найдена. Пожалуйста, подпишитесь и нажмите 'Проверить' снова.",
            reply_markup=subscription_keyboard(),
        )
