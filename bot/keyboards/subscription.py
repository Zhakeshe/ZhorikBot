from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.utils.checks import SUB_CHANNELS


def subscription_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"Подписаться {channel}", url=f"https://t.me/{channel.lstrip('@')}")]
        for channel in SUB_CHANNELS
    ]
    buttons.append([InlineKeyboardButton(text="Проверить", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
