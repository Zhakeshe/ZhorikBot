import asyncio
import os
from typing import List

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription, parse_search_query
from bot.utils.db import (
    add_moderator,
    delete_status,
    get_moderators,
    get_statuses,
    resolve_user,
    save_status,
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


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_moderator(user_id: int) -> bool:
    return user_id in get_moderators() or is_admin(user_id)


def notify_admins(message: Message, text: str) -> None:
    for admin_id in ADMIN_IDS:
        asyncio.create_task(message.bot.send_message(admin_id, text))


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
    stats = stats_by_status()
    statuses = get_statuses()
    stats_lines = "\n".join([f"{statuses.get(code, {}).get('title', code)}: {count}" for code, count in stats.items()])
    moderation_lines = "\n".join([f"• {mid}" for mid in get_moderators()]) or "нет модераторов"
    await message.answer(
        "📊 Панель администратора\n\n"
        f"Пользователи по статусам:\n{stats_lines or 'нет данных'}\n\n"
        f"Количество модераторов: {len(get_moderators())}\n{moderation_lines}\n\n"
        "Доступные команды:\n"
        "/addmod <id> — добавить модератора\n"
        "/delmod <id> — удалить модератора\n"
        "/listmods — список модераторов\n"
        "/addstatus code;title;photo;description — добавить статус\n"
        "/editstatus code field value — обновить статус (title|photo|description)\n"
        "/delstatus code — удалить статус\n"
        "/setstatus target status [proof] [comment] — изменить статус пользователя\n"
        "/logs — показать логи"
    )


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
    parsed = parse_search_query(target_raw) or target_raw
    target_id, existing_user = resolve_user(parsed)
    status_map = get_statuses()
    if status_code not in status_map:
        await message.answer("Неизвестная категория статуса. Добавьте её через /addstatus.")
        return
    user_id = None
    if existing_user:
        user_id = int(existing_user.get("id"))
    elif target_raw.isdigit():
        user_id = int(target_raw)
    elif target_raw.lower().startswith("id") and target_raw[2:].isdigit():
        user_id = int(target_raw[2:])
    elif message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
    if not user_id:
        await message.answer("Не удалось определить ID пользователя.")
        return
    username = existing_user.get("username") if existing_user else None
    if message.reply_to_message and message.reply_to_message.from_user:
        username = message.reply_to_message.from_user.username or username
    update_result = upsert_user(user_id=user_id, username=username, status=status_code, proof=proof, comment=comment, updated_by=message.from_user.id)
    log_entry = build_log(
        moderator_id=message.from_user.id,
        target_id=user_id,
        old_status=update_result["old_status"],
        new_status=status_code,
        proof=proof,
        comment=comment,
    )
    save_log(log_entry)
    await message.answer(format_status_text(update_result["user"], target_raw))
    notify_admins(
        message,
        "📢 Действие модератора:\n"
        f"Модератор: @{message.from_user.username} ({message.from_user.id})\n"
        f"Цель: @{username or 'unknown'} ({user_id})\n"
        f"Статус: {update_result['old_status']} → {status_code}\n"
        f"Пруф: {proof or '—'}\n"
        f"Комментарий: {comment or '—'}\n"
        f"Время: {log_entry['time']}",
    )


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
