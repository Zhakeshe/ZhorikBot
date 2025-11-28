import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

# =========================================
# CONFIGURATION
# =========================================
BOT_TOKEN = "8211206850:AAFhBZ2Y6q7UCU0271r3AUJL4iRfsMroGCY"

ADMIN_IDS = [7874477752]
REQUIRED_CHANNELS = ["@ZhorikBase", "@ZhorikBaseProofs"]

GROUP_LINK = "@ZhorikBase"
CHANNEL_LINK = "@ZhorikBaseProofs"
BOT_LINK = "@ZhorikBaseRobot"
FOOTER = f"\n\nГруппа: {GROUP_LINK}\nКанал: {CHANNEL_LINK}\nЛичка: {BOT_LINK}"

PHOTO_START = "https://placehold.co/800x400/0a0/fff.png?text=ZhorikBase"
PHOTO_UNKNOWN = "https://placehold.co/600x400/555/fff.png?text=Unknown"
PHOTO_VERIFIED = "https://placehold.co/600x400/2ecc71/fff.png?text=Verified"
PHOTO_DOUBTFUL = "https://placehold.co/600x400/f39c12/fff.png?text=Doubtful"
PHOTO_SCAMMER = "https://placehold.co/600x400/e74c3c/fff.png?text=Scammer"
PHOTO_GUARANTOR = "https://placehold.co/600x400/3498db/fff.png?text=Guarantor"
PHOTO_TEAM = "https://placehold.co/600x400/9b59b6/fff.png?text=Team"

DATA_PATH = Path("database.json")

STATUS_TEAM = "team"
STATUS_GUARANTOR = "guarantor"
STATUS_VERIFIED = "verified"
STATUS_UNKNOWN = "unknown"
STATUS_DOUBTFUL = "doubtful"
STATUS_SCAMMER = "scammer"

STATUS_TITLES = {
    STATUS_TEAM: "⚙ Команда бота",
    STATUS_GUARANTOR: "🛡 Гарант",
    STATUS_VERIFIED: "🟢 Проверенный",
    STATUS_UNKNOWN: "❓ Неизвестный",
    STATUS_DOUBTFUL: "🟠 Сомнительный",
    STATUS_SCAMMER: "🔴 Мошенник",
}

STATUS_DESCRIPTIONS = {
    STATUS_TEAM: "Участник команды ZhorikBase с полными полномочиями.",
    STATUS_GUARANTOR: "Авторизованный гарант антискам-проекта.",
    STATUS_VERIFIED: "Пользователь честный. Основано на репутации.",
    STATUS_UNKNOWN: "Информации недостаточно. Будьте бдительны.",
    STATUS_DOUBTFUL: "Есть сомнения. Требуется дополнительная проверка.",
    STATUS_SCAMMER: "Фиксированы жалобы. Опасность мошенничества!",
}

DEFAULT_DB: Dict[str, Any] = {
    "users": {
        "75874120": {
            "id": 75874120,
            "username": "aqrxrx",
            "status": STATUS_SCAMMER,
            "proof": "https://t.me/link",
            "comment": "много жалоб",
            "updated_by": 123456,
            "updated_at": "2025-01-01T10:00:00",
        }
    },
    "moderators": [123],
    "logs": [
        {
            "time": "2025-01-01T10:00:00",
            "moderator_id": 123,
            "target_id": 75874120,
            "old_status": "unknown",
            "new_status": STATUS_SCAMMER,
            "proof": "https://t.me/link",
            "comment": "много жалоб",
        }
    ],
}

logging.basicConfig(level=logging.INFO)
router = Router()


# =========================================
# DATABASE HELPERS
# =========================================
def ensure_db_exists() -> None:
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps(DEFAULT_DB, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    try:
        with DATA_PATH.open("r", encoding="utf-8") as f:
            existing = json.load(f)
    except json.JSONDecodeError:
        DATA_PATH.write_text(json.dumps(DEFAULT_DB, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    changed = False
    for key in ["users", "moderators", "logs"]:
        if key not in existing:
            existing[key] = DEFAULT_DB.get(key, [] if key != "users" else {})
            changed = True
    if changed:
        DATA_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def load_db() -> Dict[str, Any]:
    ensure_db_exists()
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db: Dict[str, Any]) -> None:
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_moderator(user_id: int, db: Optional[Dict[str, Any]] = None) -> bool:
    if is_admin(user_id):
        return True
    if db is None:
        db = load_db()
    return user_id in db.get("moderators", [])


def status_photo(status: str) -> str:
    return {
        STATUS_UNKNOWN: PHOTO_UNKNOWN,
        STATUS_VERIFIED: PHOTO_VERIFIED,
        STATUS_DOUBTFUL: PHOTO_DOUBTFUL,
        STATUS_SCAMMER: PHOTO_SCAMMER,
        STATUS_GUARANTOR: PHOTO_GUARANTOR,
        STATUS_TEAM: PHOTO_TEAM,
    }.get(status, PHOTO_UNKNOWN)


def status_text(status: str) -> str:
    return STATUS_DESCRIPTIONS.get(status, STATUS_DESCRIPTIONS[STATUS_UNKNOWN])


def status_title(status: str) -> str:
    return STATUS_TITLES.get(status, STATUS_TITLES[STATUS_UNKNOWN])


def get_or_create_user(db: Dict[str, Any], user_id: int, username: Optional[str]) -> Dict[str, Any]:
    key = str(user_id)
    if key not in db["users"]:
        db["users"][key] = {
            "id": user_id,
            "username": username,
            "status": STATUS_UNKNOWN,
            "proof": None,
            "comment": None,
            "updated_by": None,
            "updated_at": None,
        }
    else:
        if username and db["users"][key].get("username") != username:
            db["users"][key]["username"] = username
    return db["users"][key]


def find_user(db: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
    q = query.strip()
    if not q:
        return None
    if q.startswith("id") and q[2:].isdigit():
        return db["users"].get(q[2:])
    if q.isdigit():
        return db["users"].get(q)
    uname = q[1:] if q.startswith("@") else q
    uname = uname.lower()
    for user in db["users"].values():
        if user.get("username") and user["username"].lower() == uname:
            return user
    return None


def add_log(db: Dict[str, Any], moderator_id: int, target_id: int, old_status: str, new_status: str, proof: Optional[str], comment: Optional[str]) -> None:
    db.setdefault("logs", []).append(
        {
            "time": datetime.utcnow().isoformat(timespec="seconds"),
            "moderator_id": moderator_id,
            "target_id": target_id,
            "old_status": old_status,
            "new_status": new_status,
            "proof": proof,
            "comment": comment,
        }
    )


# =========================================
# UI HELPERS
# =========================================
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
            [InlineKeyboardButton(text="💼 Профиль", callback_data="menu_profile")],
            [InlineKeyboardButton(text="👥 Списки", callback_data="menu_lists")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")],
        ]
    )


def subscription_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Подписаться на канал", url="https://t.me/ZhorikBase")],
        [InlineKeyboardButton(text="Подписаться на пруфы", url="https://t.me/ZhorikBaseProofs")],
        [InlineKeyboardButton(text="Проверить", callback_data="check_sub")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_text(user: Dict[str, Any]) -> str:
    username = user.get("username") or "unknown"
    header = f"🔺 @{username} | id {user['id']}"
    body = f"{status_title(user['status'])}\n{status_text(user['status'])}"
    proof = f"\nПруф: {user['proof']}" if user.get("proof") else ""
    comment = f"\nКомментарий: {user['comment']}" if user.get("comment") else ""
    return header + "\n\n" + body + proof + comment + FOOTER


def status_line(user: Dict[str, Any]) -> str:
    username = user.get("username") or "unknown"
    parts = [
        f"🔺 @{username} | id {user['id']}",
        f"{status_title(user['status'])}",
        f"{status_text(user['status'])}",
    ]
    if user.get("proof"):
        parts.append(f"Пруф: {user['proof']}")
    if user.get("comment"):
        parts.append(f"Комментарий: {user['comment']}")
    return "\n".join(parts) + FOOTER


# =========================================
# SUBSCRIPTION CHECK
# =========================================
async def has_subscription(bot: Bot, user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
                return False
        except TelegramBadRequest:
            return False
        except Exception:
            return False
    return True


async def ensure_subscription_for_message(message: Message, bot: Bot) -> bool:
    ok = await has_subscription(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "Для работы с ботом необходимо подписаться на все обязательные каналы.",
            reply_markup=subscription_keyboard(),
        )
    return ok


async def ensure_subscription_for_callback(callback: CallbackQuery, bot: Bot) -> bool:
    ok = await has_subscription(bot, callback.from_user.id)
    if not ok:
        await callback.message.answer(
            "Подпишитесь на обязательные каналы, затем нажмите \"Проверить\".",
            reply_markup=subscription_keyboard(),
        )
        await callback.answer()
    return ok


# =========================================
# COMMAND HANDLERS
# =========================================
@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    bot = message.bot
    if not await ensure_subscription_for_message(message, bot):
        return
    caption = (
        "Добро пожаловать в ZhorikBase.\n"
        "База статусов пользователей: команда, гаранты, проверенные и мошенники.\n"
        "Используйте меню ниже для работы."
    )
    await message.answer_photo(photo=PHOTO_START, caption=caption, reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not await ensure_subscription_for_message(message, message.bot):
        return
    text = (
        "Доступные команды:\n"
        "/start — запуск и меню\n"
        "/help — помощь\n"
        "/info — список статусов\n"
        "/me — ваш профиль\n"
        "/search <запрос> — поиск по id/username\n"
        "/check — ответом на сообщение в чате покажет статус\n"
        "/admin — панель администратора\n"
        "/addmod <id> — добавить модератора\n"
        "/delmod <id> — удалить модератора\n"
        "/listmods — список модераторов\n"
        "/setstatus @user статус [пруф] [комментарий] — изменить статус"
    )
    await message.answer(text)


@router.message(Command("info"))
async def cmd_info(message: Message) -> None:
    if not await ensure_subscription_for_message(message, message.bot):
        return
    lines = [f"{code}: {title}" for code, title in STATUS_TITLES.items()]
    await message.answer("Статусы:\n" + "\n".join(lines))


@router.message(Command("me"))
async def cmd_me(message: Message) -> None:
    bot = message.bot
    if not await ensure_subscription_for_message(message, bot):
        return
    db = load_db()
    user = get_or_create_user(db, message.from_user.id, message.from_user.username)
    save_db(db)
    await message.answer_photo(photo=status_photo(user["status"]), caption=profile_text(user))


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject) -> None:
    if not await ensure_subscription_for_message(message, message.bot):
        return
    query = (command.args or "").strip()
    if not query:
        await message.answer("Укажите запрос: /search <id|username|@username|id123>")
        return
    db = load_db()
    found = find_user(db, query)
    if not found:
        found = {
            "id": query.lstrip("@"),
            "username": query.lstrip("@"),
            "status": STATUS_UNKNOWN,
            "proof": None,
            "comment": None,
        }
    await message.answer(status_line(found))


@router.message(Command("check"))
async def cmd_check(message: Message) -> None:
    bot = message.bot
    if not await ensure_subscription_for_message(message, bot):
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Команда работает только в ответ на сообщение пользователя.")
        return
    target = message.reply_to_message.from_user
    db = load_db()
    user = get_or_create_user(db, target.id, target.username)
    save_db(db)
    await message.answer(status_line(user))


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    bot = message.bot
    if not await ensure_subscription_for_message(message, bot):
        return
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав для доступа к админ-панели.")
        return
    db = load_db()
    stats: Dict[str, int] = {code: 0 for code in STATUS_TITLES.keys()}
    for user in db.get("users", {}).values():
        stats[user.get("status", STATUS_UNKNOWN)] = stats.get(user.get("status", STATUS_UNKNOWN), 0) + 1
    stat_lines = [f"{status_title(code)}: {count}" for code, count in stats.items()]
    info_lines = [
        "Админ-панель:",
        *stat_lines,
        f"Модераторов: {len(db.get('moderators', []))}",
        "Команды: /addmod /delmod /listmods /setstatus",
    ]
    await message.answer("\n".join(info_lines))


@router.message(Command("addmod"))
async def cmd_addmod(message: Message, command: CommandObject) -> None:
    if not await ensure_subscription_for_message(message, message.bot):
        return
    if not is_admin(message.from_user.id):
        await message.answer("Только администратор может добавлять модераторов.")
        return
    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Использование: /addmod <user_id>")
        return
    mod_id = int(args)
    db = load_db()
    if mod_id in db.get("moderators", []):
        await message.answer("Пользователь уже модератор.")
        return
    db.setdefault("moderators", []).append(mod_id)
    save_db(db)
    await message.answer(f"Модератор {mod_id} добавлен.")


@router.message(Command("delmod"))
async def cmd_delmod(message: Message, command: CommandObject) -> None:
    if not await ensure_subscription_for_message(message, message.bot):
        return
    if not is_admin(message.from_user.id):
        await message.answer("Только администратор может удалять модераторов.")
        return
    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Использование: /delmod <user_id>")
        return
    mod_id = int(args)
    db = load_db()
    if mod_id not in db.get("moderators", []):
        await message.answer("Пользователь не является модератором.")
        return
    db["moderators"] = [m for m in db.get("moderators", []) if m != mod_id]
    save_db(db)
    await message.answer(f"Модератор {mod_id} удалён.")


@router.message(Command("listmods"))
async def cmd_listmods(message: Message) -> None:
    if not await ensure_subscription_for_message(message, message.bot):
        return
    if not is_admin(message.from_user.id):
        await message.answer("Доступно только администраторам.")
        return
    db = load_db()
    mods = db.get("moderators", [])
    text = "Список модераторов:\n" + "\n".join(str(m) for m in mods) if mods else "Модераторов пока нет."
    await message.answer(text)


@router.message(Command("setstatus"))
async def cmd_setstatus(message: Message, command: CommandObject) -> None:
    bot = message.bot
    if not await ensure_subscription_for_message(message, bot):
        return
    db = load_db()
    if not is_moderator(message.from_user.id, db):
        await message.answer("Недостаточно прав для изменения статуса.")
        return
    args = (command.args or "").strip().split()
    if len(args) < 2:
        await message.answer("Использование: /setstatus @user статус [пруф] [комментарий]")
        return
    target_raw, new_status, *rest = args
    if new_status not in STATUS_TITLES:
        await message.answer("Неизвестный статус. Используйте /info для списка.")
        return
    target_user: Optional[Dict[str, Any]] = None
    target_id: Optional[int] = None
    if target_raw.isdigit():
        target_id = int(target_raw)
        target_user = get_or_create_user(db, target_id, None)
    else:
        target_user = find_user(db, target_raw)
        if target_user:
            target_id = target_user["id"]
    if target_user is None or target_id is None:
        await message.answer("Пользователь не найден. Укажите корректный id или известный username.")
        return
    proof = rest[0] if rest else None
    comment = " ".join(rest[1:]) if len(rest) > 1 else None
    old_status = target_user.get("status", STATUS_UNKNOWN)
    target_user.update(
        {
            "status": new_status,
            "proof": proof,
            "comment": comment,
            "updated_by": message.from_user.id,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
    )
    db["users"][str(target_id)] = target_user
    add_log(db, message.from_user.id, target_id, old_status, new_status, proof, comment)
    save_db(db)
    notify_text = (
        "📢 Действие модератора:\n"
        f"Модератор: @{message.from_user.username or 'unknown'} ({message.from_user.id})\n"
        f"Цель: @{target_user.get('username') or 'unknown'} ({target_id})\n"
        f"Статус: {status_title(old_status)} → {status_title(new_status)}\n"
        f"Пруф: {proof or '—'}\n"
        f"Комментарий: {comment or '—'}\n"
        f"Время: {target_user['updated_at']}"
    )
    await message.answer(status_line(target_user))
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, notify_text)
        except Exception:
            logging.warning("Не удалось отправить уведомление администратору %s", admin_id)


# =========================================
# INLINE BUTTONS
# =========================================
@router.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: CallbackQuery) -> None:
    bot = callback.bot
    if await has_subscription(bot, callback.from_user.id):
        await callback.message.answer("Подписка подтверждена. Можно продолжать работу.")
    else:
        await callback.message.answer("Подписка не найдена. Проверьте, что подписаны на оба канала.")
    await callback.answer()


@router.callback_query(F.data == "menu_search")
async def callback_menu_search(callback: CallbackQuery) -> None:
    if not await ensure_subscription_for_callback(callback, callback.bot):
        return
    await callback.message.answer("Введите запрос командой /search <id|username> для проверки статуса.")
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def callback_menu_profile(callback: CallbackQuery) -> None:
    bot = callback.bot
    if not await ensure_subscription_for_callback(callback, bot):
        return
    db = load_db()
    user = get_or_create_user(db, callback.from_user.id, callback.from_user.username)
    save_db(db)
    await callback.message.answer_photo(photo=status_photo(user["status"]), caption=profile_text(user))
    await callback.answer()


@router.callback_query(F.data == "menu_lists")
async def callback_menu_lists(callback: CallbackQuery) -> None:
    if not await ensure_subscription_for_callback(callback, callback.bot):
        return
    db = load_db()
    statuses: Dict[str, List[str]] = {code: [] for code in STATUS_TITLES}
    for user in db.get("users", {}).values():
        uname = f"@{user.get('username')}" if user.get("username") else str(user.get("id"))
        statuses[user.get("status", STATUS_UNKNOWN)].append(uname)
    lines = []
    for code, users in statuses.items():
        names = ", ".join(users) if users else "—"
        lines.append(f"{status_title(code)}: {names}")
    await callback.message.answer("Списки по статусам:\n" + "\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def callback_menu_help(callback: CallbackQuery) -> None:
    if not await ensure_subscription_for_callback(callback, callback.bot):
        return
    await callback.message.answer("Используйте /help чтобы увидеть все возможности бота.")
    await callback.answer()


# =========================================
# INLINE MODE
# =========================================
@router.inline_query()
async def inline_query_handler(inline_query: InlineQuery) -> None:
    bot = inline_query.bot
    query = inline_query.query.strip()
    allowed = await has_subscription(bot, inline_query.from_user.id)
    if not allowed:
        result = InlineQueryResultArticle(
            id="subscribe",
            title="Подписка обязательна",
            description="Подпишитесь на каналы для использования бота",
            input_message_content=InputTextMessageContent(
                message_text="Подпишитесь на @ZhorikBase и @ZhorikBaseProofs для использования бота."
            ),
        )
        await inline_query.answer([result], cache_time=1)
        return
    db = load_db()
    user = find_user(db, query) if query else get_or_create_user(db, inline_query.from_user.id, inline_query.from_user.username)
    if not user:
        user = {
            "id": query or inline_query.from_user.id,
            "username": query or inline_query.from_user.username,
            "status": STATUS_UNKNOWN,
            "proof": None,
            "comment": None,
        }
    result = InlineQueryResultArticle(
        id="status_result",
        title=status_title(user.get("status", STATUS_UNKNOWN)),
        description=f"@{user.get('username') or 'unknown'} | {user.get('id')}",
        input_message_content=InputTextMessageContent(message_text=status_line(user)),
    )
    await inline_query.answer([result], cache_time=1)


# =========================================
# APPLICATION STARTUP
# =========================================
async def main() -> None:
    ensure_db_exists()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
