from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard(show_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [InlineKeyboardButton(text="💼 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="👥 Списки", callback_data="menu_lists")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")],
    ]
    if show_admin:
        buttons.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="menu_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
