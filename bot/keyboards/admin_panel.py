from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")],
            [InlineKeyboardButton(text="👥 Модераторы", callback_data="admin_mods")],
            [InlineKeyboardButton(text="➕ Добавить модератора", callback_data="admin_addmod")],
            [InlineKeyboardButton(text="➖ Удалить модератора", callback_data="admin_delmod")],
            [InlineKeyboardButton(text="📂 Статусы", callback_data="admin_statuses")],
            [InlineKeyboardButton(text="🆕 Добавить статус", callback_data="admin_addstatus")],
            [InlineKeyboardButton(text="✏️ Редактировать статус", callback_data="admin_editstatus")],
            [InlineKeyboardButton(text="🗑 Удалить статус", callback_data="admin_delstatus")],
            [InlineKeyboardButton(text="⚙️ Изменить статус пользователя", callback_data="admin_setstatus")],
            [InlineKeyboardButton(text="📒 Логи", callback_data="admin_logs")],
        ]
    )
