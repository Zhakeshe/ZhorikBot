import asyncio
import os
from typing import Dict, List, Optional, Tuple

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin_panel import admin_panel_keyboard
from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription, parse_search_query
from bot.utils.db import (
    add_moderator,
    delete_status,
    get_admins,
    get_moderators,
    get_statuses,
    resolve_user,
    save_status,
    seed_admins,
    stats_by_status,
    update_status,
    upsert_user,
)
from bot.utils.logs import build_log, save_log
from bot.utils.status import format_status_text

router = Router()

ADMIN_IDS: List[int] = [123]
admin_env = os.environ.get("ADMIN_IDS")
if admin_env:
    ADMIN_IDS = [int(x) for x in admin_env.split(",") if x.strip().isdigit()]
seed_admins(ADMIN_IDS)


def is_admin(user_id: int) -> bool:
    return user_id in set(get_admins()) or user_id in ADMIN_IDS


def is_moderator(user_id: int) -> bool:
    return user_id in get_moderators() or is_admin(user_id)


def notify_admins(message: Message, *parts: str) -> None:
    text = "".join(parts)
    targets = set(get_admins()) | set(ADMIN_IDS)
    for admin_id in targets:
        asyncio.create_task(message.bot.send_message(admin_id, text))


def apply_status_change(
    actor_id: int,
    message: Message,
    target_raw: str,
    status_code: str,
    proof: str,
    comment: str,
    reply_user_id: Optional[int],
    reply_username: Optional[str],
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    parsed = parse_search_query(target_raw) or target_raw
    _, existing_user = resolve_user(parsed)
    status_map = get_statuses()
    if status_code not in status_map:
        return None, "Неизвестная категория статуса. Добавьте её через /addstatus."

    user_id = None
    if existing_user:
        user_id = int(existing_user.get("id"))
    elif target_raw.isdigit():
        user_id = int(target_raw)
    elif target_raw.lower().startswith("id") and target_raw[2:].isdigit():
        user_id = int(target_raw[2:])
    elif reply_user_id:
        user_id = reply_user_id
    if not user_id:
        return None, "Не удалось определить ID пользователя."

    username = existing_user.get("username") if existing_user else None
    if reply_username:
        username = reply_username or username
    update_result = upsert_user(
        user_id=user_id,
        username=username,
        status=status_code,
        proof=proof,
        comment=comment,
        updated_by=actor_id,
    )
    log_entry = build_log(
        moderator_id=actor_id,
        target_id=user_id,
        old_status=update_result["old_status"],
        new_status=status_code,
        proof=proof,
        comment=comment,
    )
    save_log(log_entry)
    notify_admins(
        message,
        "📢 Действие модератора:\n",
        f"Модератор: @{message.from_user.username} ({message.from_user.id})\n",
        f"Цель: @{username or 'unknown'} ({user_id})\n",
        f"Статус: {update_result['old_status']} → {status_code}\n",
        f"Пруф: {proof or '—'}\n",
        f"Комментарий: {comment or '—'}\n",
        f"Время: {log_entry['time']}",
    )
    return update_result["user"], None


def build_admin_panel_text() -> str:
    stats = stats_by_status()
    statuses = get_statuses()
    stats_lines = "\n".join([f"{statuses.get(code, {}).get('title', code)}: {count}" for code, count in stats.items()])
    moderation_lines = "\n".join([f"• {mid}" for mid in get_moderators()]) or "нет модераторов"
    admin_lines = "\n".join([f"• {aid}" for aid in get_admins()]) or "нет админов"
    return (
        "📊 Панель администратора\n\n"
        f"Пользователи по статусам:\n{stats_lines or 'нет данных'}\n\n"
        f"Администраторы: {len(get_admins())}\n{admin_lines}\n\n"
        f"Количество модераторов: {len(get_moderators())}\n{moderation_lines}\n\n"
        "Управление через кнопки ниже:\n"
        "• 📊 Обновить панель\n"
        "• 👥 Модераторы: добавить/удалить/список\n"
        "• 🛡 Статус-категории: добавить/изменить/удалить\n"
        "• ⚙️ Изменить статус пользователя\n"
        "• 🧾 Логи: просмотр последних записей\n\n"
        "Команды больше не требуются — все действия доступны в инлайн-панели."
    )


PENDING_ACTIONS: Dict[int, str] = {}


def set_pending(user_id: int, action: str) -> None:
    PENDING_ACTIONS[user_id] = action


def pop_pending(user_id: int) -> str | None:
    return PENDING_ACTIONS.pop(user_id, None)


@router.message(F.text, lambda message: message.from_user and message.from_user.id in PENDING_ACTIONS)
async def handle_pending_actions(message: Message) -> None:
    action = PENDING_ACTIONS.get(message.from_user.id)
    if not action:
        return
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        pop_pending(message.from_user.id)
        await message.answer("Недостаточно прав.")
        return

    text = message.text.strip()
    if action == "addmod":
        if not text.isdigit():
            await message.answer("Введите числовой ID модератора.")
            return
        mod_id = int(text)
        add_moderator(mod_id)
        pop_pending(message.from_user.id)
        await message.answer(f"Модератор {mod_id} добавлен.")
        return

    if action == "delmod":
        if not text.isdigit():
            await message.answer("Введите числовой ID модератора.")
            return
        mod_id = int(text)
        from bot.utils.db import remove_moderator

        removed = remove_moderator(mod_id)
        pop_pending(message.from_user.id)
        if removed:
            await message.answer(f"Модератор {mod_id} удален.")
        else:
            await message.answer("Модератор не найден.")
        return

    if action == "addstatus":
        if text.count(";") < 3:
            await message.answer("Форма: code;title;photo;description")
            return
        code, title, photo, description = [part.strip() for part in text.split(";", 3)]
        save_status(code, title, description, photo)
        pop_pending(message.from_user.id)
        await message.answer(f"Статус {title} добавлен.")
        return

    if action == "editstatus":
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Формат: code field value")
            return
        code, field, value = parts[0], parts[1], parts[2]
        if field not in {"title", "photo", "description"}:
            await message.answer("Поле должно быть title, photo или description.")
            return
        updated = update_status(code, **{field: value})
        pop_pending(message.from_user.id)
        if updated:
            await message.answer("Статус обновлен.")
        else:
            await message.answer("Категория не найдена.")
        return

    if action == "delstatus":
        code = text
        removed = delete_status(code)
        pop_pending(message.from_user.id)
        if removed:
            await message.answer("Статус удален.")
        else:
            await message.answer("Нельзя удалить статус: либо не найден, либо есть пользователи в этой категории.")
        return

    if action == "setstatus":
        if len(text.split()) < 2:
            await message.answer("Формат: target status [proof] [comment]")
            return
        parts = text.split()
        target_raw = parts[0]
        status_code = parts[1]
        proof = parts[2] if len(parts) > 2 else ""
        comment = " ".join(parts[3:]) if len(parts) > 3 else ""
        user, error = apply_status_change(
            actor_id=message.from_user.id,
            message=message,
            target_raw=target_raw,
            status_code=status_code,
            proof=proof,
            comment=comment,
            reply_user_id=None,
            reply_username=None,
        )
        if error:
            await message.answer(error)
            return
        pop_pending(message.from_user.id)
        await message.answer(format_status_text(user, target_raw))
        return


@router.message(Command("admin"))
async def handle_admin(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Команда доступна только админам.")
        return
    await message.answer(build_admin_panel_text(), reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "menu_admin")
async def handle_menu_admin(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Команда доступна только админам.")
        return
    await call.message.answer(build_admin_panel_text(), reply_markup=admin_panel_keyboard())


@router.message(Command("addmod"))
async def handle_addmod(message: Message, command: CommandObject) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Только админы могут управлять модераторами.")
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Укажите ID модератора: /addmod 123456")
        return
    mod_id = int(command.args.strip())
    add_moderator(mod_id)
    await message.answer(f"Модератор {mod_id} добавлен.")


@router.message(Command("delmod"))
async def handle_delmod(message: Message, command: CommandObject) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Только админы могут управлять модераторами.")
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Укажите ID модератора: /delmod 123456")
        return
    mod_id = int(command.args.strip())
    from bot.utils.db import remove_moderator

    removed = remove_moderator(mod_id)
    if removed:
        await message.answer(f"Модератор {mod_id} удален.")
    else:
        await message.answer("Модератор не найден.")


@router.callback_query(F.data == "admin_mods")
async def handle_admin_mods(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    mods = get_moderators()
    text = "Модераторы:\n" + "\n".join([f"• {mid}" for mid in mods]) if mods else "Список модераторов пуст."
    await call.message.answer(text)


@router.callback_query(F.data == "admin_addmod")
async def handle_admin_addmod_prompt(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    set_pending(call.from_user.id, "addmod")
    await call.message.answer("Введите ID модератора в ответ на это сообщение.")


@router.callback_query(F.data == "admin_delmod")
async def handle_admin_delmod_prompt(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    set_pending(call.from_user.id, "delmod")
    await call.message.answer("Введите ID модератора для удаления.")


@router.message(Command("listmods"))
async def handle_listmods(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Только админы могут управлять модераторами.")
        return
    mods = get_moderators()
    await message.answer("Модераторы:\n" + "\n".join([f"• {mid}" for mid in mods]) if mods else "Список модераторов пуст.")


@router.message(Command("addstatus"))
async def handle_addstatus(message: Message, command: CommandObject) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return
    if not command.args or command.args.count(";") < 3:
        await message.answer("Формат: /addstatus code;title;photo;description")
        return
    code, title, photo, description = [part.strip() for part in command.args.split(";", 3)]
    save_status(code, title, description, photo)
    await message.answer(f"Статус {title} добавлен.")


@router.message(Command("editstatus"))
async def handle_editstatus(message: Message, command: CommandObject) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return
    if not command.args or len(command.args.split()) < 3:
        await message.answer("Формат: /editstatus code field value")
        return
    parts = command.args.split(maxsplit=2)
    code, field, value = parts[0], parts[1], parts[2]
    kwargs = {field: value}
    if field not in {"title", "photo", "description"}:
        await message.answer("Поле должно быть title, photo или description.")
        return
    updated = update_status(code, **kwargs)
    if updated:
        await message.answer("Статус обновлен.")
    else:
        await message.answer("Категория не найдена.")


@router.message(Command("delstatus"))
async def handle_delstatus(message: Message, command: CommandObject) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return
    if not command.args:
        await message.answer("Укажите код статуса: /delstatus verified")
        return
    code = command.args.strip()
    removed = delete_status(code)
    if removed:
        await message.answer("Статус удален.")
    else:
        await message.answer("Нельзя удалить статус: либо не найден, либо есть пользователи в этой категории.")


@router.callback_query(F.data == "admin_statuses")
async def handle_admin_statuses(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    statuses = get_statuses()
    if not statuses:
        await call.message.answer("Статусы не найдены.")
        return
    lines = [
        f"• {code}: {data.get('title')}\n  {data.get('description')}\n  Фото: {data.get('photo')}" for code, data in statuses.items()
    ]
    await call.message.answer("Существующие статусы:\n" + "\n\n".join(lines))


@router.callback_query(F.data == "admin_addstatus")
async def handle_admin_addstatus_prompt(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    set_pending(call.from_user.id, "addstatus")
    await call.message.answer("Введите новую категорию: code;title;photo;description")


@router.callback_query(F.data == "admin_editstatus")
async def handle_admin_editstatus_prompt(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    set_pending(call.from_user.id, "editstatus")
    await call.message.answer("Введите данные: code field value (field = title|photo|description)")


@router.callback_query(F.data == "admin_delstatus")
async def handle_admin_delstatus_prompt(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    set_pending(call.from_user.id, "delstatus")
    await call.message.answer("Введите код статуса для удаления.")


@router.callback_query(F.data == "admin_setstatus")
async def handle_admin_setstatus_prompt(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_moderator(call.from_user.id):
        await call.message.answer("Команда доступна модераторам и админам.")
        return
    set_pending(call.from_user.id, "setstatus")
    await call.message.answer("Введите: target status [proof] [comment]")


@router.message(Command("setstatus"))
async def handle_setstatus(message: Message, command: CommandObject) -> None:
    if not is_moderator(message.from_user.id):
        await message.answer("Команда доступна модераторам и админам.")
        return
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not command.args or len(command.args.split()) < 2:
        await message.answer("Формат: /setstatus target status [proof] [comment]")
        return
    args = command.args.split()
    target_raw = args[0]
    status_code = args[1]
    proof = args[2] if len(args) > 2 else ""
    comment = " ".join(args[3:]) if len(args) > 3 else ""
    user, error = apply_status_change(
        actor_id=message.from_user.id,
        message=message,
        target_raw=target_raw,
        status_code=status_code,
        proof=proof,
        comment=comment,
        reply_user_id=message.reply_to_message.from_user.id if message.reply_to_message and message.reply_to_message.from_user else None,
        reply_username=message.reply_to_message.from_user.username if message.reply_to_message and message.reply_to_message.from_user else None,
    )
    if error:
        await message.answer(error)
        return
    await message.answer(format_status_text(user, target_raw))


@router.message(Command("logs"))
async def handle_logs(message: Message) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return
    from bot.utils.db import get_log_entries

    entries = get_log_entries()
    if not entries:
        await message.answer("Логи пусты.")
        return
    last_entries = entries[-10:]
    lines = []
    for entry in last_entries:
        lines.append(
            "📒 Log:\n"
            f"• Модератор: {entry['moderator_id']}\n"
            f"• Кому: {entry['target_id']}\n"
            f"• Старый статус → Новый статус: {entry['old_status']} → {entry['new_status']}\n"
            f"• Пруф: {entry.get('proof', '—')}\n"
            f"• Комментарий: {entry.get('comment', '—')}\n"
            f"• Время: {entry['time']}"
        )
    await message.answer("\n\n".join(lines))


@router.callback_query(F.data == "admin_logs")
async def handle_admin_logs(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    from bot.utils.db import get_log_entries

    entries = get_log_entries()
    if not entries:
        await call.message.answer("Логи пусты.")
        return
    last_entries = entries[-10:]
    lines = []
    for entry in last_entries:
        lines.append(
            "📒 Log:\n"
            f"• Модератор: {entry['moderator_id']}\n"
            f"• Кому: {entry['target_id']}\n"
            f"• Старый статус → Новый статус: {entry['old_status']} → {entry['new_status']}\n"
            f"• Пруф: {entry.get('proof', '—')}\n"
            f"• Комментарий: {entry.get('comment', '—')}\n"
            f"• Время: {entry['time']}"
        )
    await call.message.answer("\n\n".join(lines))


@router.callback_query(F.data == "admin_refresh")
async def handle_admin_refresh(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав.")
        return
    await call.message.answer(build_admin_panel_text(), reply_markup=admin_panel_keyboard())
