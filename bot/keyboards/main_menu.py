from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
            [InlineKeyboardButton(text="💼 Профиль", callback_data="menu_profile")],
            [InlineKeyboardButton(text="👥 Списки", callback_data="menu_lists")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")],
        ]
    )
