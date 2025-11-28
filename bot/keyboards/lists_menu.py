from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.utils.db import get_statuses


def lists_keyboard() -> InlineKeyboardMarkup:
    statuses = get_statuses()
    rows = []
    for code, status in statuses.items():
        rows.append([InlineKeyboardButton(text=status.get("title", code), callback_data=f"list_{code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="Нет категорий", callback_data="noop")]])
