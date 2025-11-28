
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties

# =========================
# CONFIG
# =========================

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"

# Админдар ID (өз Telegram ID-ңді осында жаз)
ADMIN_IDS = [
    123456789
]

# Міндетті подписка арналары
REQUIRED_CHANNELS = ["@ZhorikBase", "@ZhorikBaseProofs"]

# Текст футер (барлық статус астында)
GROUP_LINK = "@ZhorikBase"
CHANNEL_LINK = "@ZhorikBaseProofs"
BOT_LINK = "@ZhorikBaseRobot"

FOOTER = f"\n\nГруппа: {GROUP_LINK}\nКанал: {CHANNEL_LINK}\nЛичка: {BOT_LINK}"

# Фото file_id немесе URL — сен кейін өзіңе керекшесін қоясың
PHOTO_UNKNOWN = "UNKNOWN_PHOTO_FILE_ID"
PHOTO_VERIFIED = "VERIFIED_PHOTO_FILE_ID"
PHOTO_DOUBTFUL = "DOUBTFUL_PHOTO_FILE_ID"
PHOTO_SCAMMER = "SCAMMER_PHOTO_FILE_ID"
PHOTO_GUARANTOR = "GUARANTOR_PHOTO_FILE_ID"
PHOTO_TEAM = "TEAM_PHOTO_FILE_ID"

DATA_PATH = "database.json"

# Статус кодтары
STATUS_TEAM = "team"
STATUS_GUARANTOR = "guarantor"
STATUS_VERIFIED = "verified"
STATUS_UNKNOWN = "unknown"
STATUS_DOUBTFUL = "doubtful"
STATUS_SCAMMER = "scammer"

STATUS_ORDER = [
    STATUS_TEAM,
    STATUS_GUARANTOR,
    STATUS_VERIFIED,
    STATUS_UNKNOWN,
    STATUS_DOUBTFUL,
    STATUS_SCAMMER,
]

STATUS_TITLES = {
    STATUS_TEAM: "⚙️ Команда бота",
    STATUS_GUARANTOR: "🛡 Гарант антискам-базы",
    STATUS_VERIFIED: "🟢 Проверенный пользователь",
    STATUS_UNKNOWN: "❓ Неизвестный пользователь",
    STATUS_DOUBTFUL: "🟠 Пользователь сомнителен",
    STATUS_SCAMMER: "🔴 Мошенник",
}

# =========================
# DB HELPERS
# =========================

def load_db() -> Dict[str, Any]:
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        db = {
            "users": {},        # str(tg_id) -> info
            "moderators": [],   # list of ids
            "logs": []          # модератор әрекеттері
        }
        save_db(db)
        return db

def save_db(db: Dict[str, Any]) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_moderator(user_id: int, db: Optional[Dict[str, Any]] = None) -> bool:
    if is_admin(user_id):
        return True
    if db is None:
        db = load_db()
    return user_id in db.get("moderators", [])


def get_user_record(db: Dict[str, Any], tg_id: int, username: Optional[str] = None) -> Dict[str, Any]:
    key = str(tg_id)
    user = db["users"].get(key)
    if not user:
        user = {
            "id": tg_id,
            "username": username,
            "status": STATUS_UNKNOWN,
            "proof": None,
            "comment": None,
            "updated_by": None,
            "updated_at": None,
        }
        db["users"][key] = user
    else:
        # username жаңарту
        if username and user.get("username") != username:
            user["username"] = username
    return user


def find_user_by_query(db: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
    q = query.strip()
    if not q:
        return None

    # ID арқылы (id123456 немесе жай 123456)
    if q.startswith("id") and q[2:].isdigit():
        tg_id = int(q[2:])
        return db["users"].get(str(tg_id))

    if q.isdigit():
        return db["users"].get(q)

    # @username арқылы
    if q.startswith("@"):
        uname = q[1:].lower()
    else:
        uname = q.lower()

    for u in db["users"].values():
        if u.get("username") and u["username"].lower() == uname:
            return u

    # Базада жоқ болса None -> неизвестный
    return None


def log_action(
    moderator_id: int,
    target_id: int,
    old_status: str,
    new_status: str,
    proof: Optional[str],
    comment: Optional[str],
) -> Dict[str, Any]:
    db = load_db()
    entry = {
        "time": datetime.utcnow().isoformat(),
        "moderator_id": moderator_id,
        "target_id": target_id,
        "old_status": old_status,
        "new_status": new_status,
        "proof": proof,
        "comment": comment,
    }
    db.setdefault("logs", []).append(entry)
    save_db(db)
    return entry


# =========================
# TEXТТЕР / КӨРІНІС
# =========================

def build_status_caption(user: Dict[str, Any]) -> str:
    username = user.get("username")
    tg_id = user.get("id")
    status = user.get("status", STATUS_UNKNOWN)
    proof = user.get("proof")
    title = STATUS_TITLES.get(status, STATUS_TITLES[STATUS_UNKNOWN])

    header_line = ""
    if status == STATUS_SCAMMER:
        header_line = f"🔴 {username or 'не указан'} | id {tg_id}\n\n"
    else:
        header_line = f"🔺 @{username or 'не указан'} | id {tg_id}\n\n"

    body = ""
    if status == STATUS_UNKNOWN:
        body = (
            f"⚪️ Пользователь @{username or 'не указан'} не найден в @ZhorikBase. "
            "Рекомендуется быть осторожным и использовать услуги проверенных гарантов - /mm."
        )
    elif status == STATUS_VERIFIED:
        body = (
            "🟢 Пользователь является честным! Мнение основано на его репутации. "
            "Администрация @ZhorikBase не несёт ответственности за данного пользователя."
        )
    elif status == STATUS_DOUBTFUL:
        body = (
            "⚠️ Замечен в неадекватном поведении и нарушении норм общения. "
            "Имеет сомнительную репутацию. Рекомендуется проявлять осторожность."
        )
    elif status == STATUS_SCAMMER:
        body = (
            "❌ Пользователь замечен в мошенничестве! Найден в базе @ZhorikBase. "
            "Ни в коем случае не взаимодействуйте с данным пользователем.❗️"
        )
    elif status == STATUS_GUARANTOR:
        body = (
            "🛡 Гарант от @ZhorikBase. Пользователь подтверждён как надёжный гарант. "
            "Проверен базой, жалоб не зафиксировано."
        )
    elif status == STATUS_TEAM:
        body = (
            "💎 Официальный представитель @ZhorikBase. Работает в команде бота. "
            "Все действия — подлинны."
        )
    else:
        body = "Статус неизвестен."

    proof_text = ""
    if proof:
        proof_text = f"\n\nПруфы: {proof}"

    return header_line + body + proof_text + FOOTER


def status_photo_id(status: str) -> str:
    if status == STATUS_SCAMMER:
        return PHOTO_SCAMMER
    if status == STATUS_VERIFIED:
        return PHOTO_VERIFIED
    if status == STATUS_DOUBTFUL:
        return PHOTO_DOUBTFUL
    if status == STATUS_GUARANTOR:
        return PHOTO_GUARANTOR
    if status == STATUS_TEAM:
        return PHOTO_TEAM
    return PHOTO_UNKNOWN


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
            [InlineKeyboardButton(text="💼 Профиль", callback_data="menu_profile")],
            [InlineKeyboardButton(text="👥 Списки", callback_data="menu_lists")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")],
        ]
    )


def subscribe_kb() -> InlineKeyboardMarkup:
    rows = []
    for ch in REQUIRED_CHANNELS:
        rows.append([InlineKeyboardButton(text=f"Подписаться на {ch}", url=f"https://t.me/{ch.lstrip('@')}")])
    rows.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================
# FSM
# =========================

class SearchStates(StatesGroup):
    waiting_query = State()


# =========================
# BOT INIT
# =========================

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)


# =========================
# SUB CHECK
# =========================

async def check_subscription(user_id: int) -> bool:
    if not REQUIRED_CHANNELS:
        return True
    for ch in REQUIRED_CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ("member", "administrator", "creator"):
                continue
            return False
        except Exception:
            # канал жабық болса — тексермейміз
            return True
    return True


async def ensure_subscribed(message: Message) -> bool:
    ok = await check_subscription(message.from_user.id)
    if ok:
        return True
    await message.answer(
        "Перед использованием бота подпишитесь на наши каналы:",
        reply_markup=subscribe_kb(),
    )
    return False


# =========================
# HANDLERS
# =========================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not await ensure_subscribed(message):
        return
    await state.clear()
    await message.answer_photo(
        photo=PHOTO_UNKNOWN,
        caption="👋 Привет! Я анти-скам бот ZhorikBase.\nИспользуйте меню ниже для проверки пользователей.",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery):
    ok = await check_subscription(call.from_user.id)
    if ok:
        await call.message.edit_text("✅ Подписка успешно проверена! Можете пользоваться ботом.", reply_markup=main_menu_kb())
    else:
        await call.answer("Подписка ещё не оформлена.", show_alert=True)


@router.callback_query(F.data == "menu_help")
async def cb_help(call: CallbackQuery):
    text = (
        "📌 Основные команды:\n"
        "/search — 🔍 Найти пользователя\n"
        "/me — 📊 Проверить свой статус\n"
        "/help — ❓ Показать это меню\n"
        "/info — ⚙️ Показать меню статусов\n\n"
        "🔍 Способы поиска:\n"
        "• По ID — <code>id123456789</code>\n"
        "• По нику — <code>@username</code>\n\n"
        "✅ В группах доступно: /check (по реплаю)\n"
    )
    await call.message.edit_text(text, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not await ensure_subscribed(message):
        return
    await cb_help(CallbackQuery(message=message, from_user=message.from_user, id="0", chat_instance="0", data="menu_help"))


@router.callback_query(F.data == "menu_profile")
async def cb_profile(call: CallbackQuery):
    db = load_db()
    u = get_user_record(db, call.from_user.id, call.from_user.username)
    save_db(db)
    caption = build_status_caption(u)
    await call.message.edit_media(
        media={"type": "photo", "media": status_photo_id(u["status"]), "caption": caption},
        reply_markup=main_menu_kb()
    )


@router.message(Command("me"))
async def cmd_me(message: Message):
    if not await ensure_subscribed(message):
        return
    db = load_db()
    u = get_user_record(db, message.from_user.id, message.from_user.username)
    save_db(db)
    await message.answer_photo(
        photo=status_photo_id(u["status"]),
        caption=build_status_caption(u),
    )


@router.callback_query(F.data == "menu_search")
async def cb_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_query)
    await call.message.edit_text("✏️ Введите @username или id123456789 для поиска пользователя:", reply_markup=main_menu_kb())


@router.message(SearchStates.waiting_query)
async def process_search_query(message: Message, state: FSMContext):
    if not await ensure_subscribed(message):
        return
    db = load_db()
    user = find_user_by_query(db, message.text.strip())
    if user is None:
        # неизвестный
        # query-ден username/id аламыз
        txt = message.text.strip()
        username = None
        tg_id = None
        if txt.startswith("@"):
            username = txt[1:]
        elif txt.startswith("id") and txt[2:].isdigit():
            tg_id = int(txt[2:])
        elif txt.isdigit():
            tg_id = int(txt)

        user = {
            "id": tg_id or 0,
            "username": username or "не указан",
            "status": STATUS_UNKNOWN,
            "proof": None,
        }

    await message.answer_photo(
        photo=status_photo_id(user["status"]),
        caption=build_status_caption(user),
    )
    await state.clear()


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    if not await ensure_subscribed(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) == 1:
        await state.set_state(SearchStates.waiting_query)
        await message.answer("✏️ Отправьте @username или id123456789:")
        return
    db = load_db()
    user = find_user_by_query(db, args[1])
    if user is None:
        txt = args[1].strip()
        username = None
        tg_id = None
        if txt.startswith("@"):
            username = txt[1:]
        elif txt.startswith("id") and txt[2:].isdigit():
            tg_id = int(txt[2:])
        elif txt.isdigit():
            tg_id = int(txt)

        user = {
            "id": tg_id or 0,
            "username": username or "не указан",
            "status": STATUS_UNKNOWN,
            "proof": None,
        }
    await message.answer_photo(
        photo=status_photo_id(user["status"]),
        caption=build_status_caption(user),
    )
    await state.clear()


@router.message(Command("info"))
async def cmd_info(message: Message):
    if not await ensure_subscribed(message):
        return
    text = (
        "Вот список возможных статусов пользователей в @ZhorikBase:\n\n"
        "1. ⚙️ Команда бота — Официальный представитель, работает в команде.\n"
        "2. 🛡 Гарант антискам-базы — Надёжный гарант, жалоб нет.\n"
        "3. 🟢 Проверенный пользователь — Репутация положительная.\n"
        "4. ❓ Неизвестный пользователь — Нет данных, будьте осторожны.\n"
        "5. 🟠 Пользователь сомнителен — Замечен в нарушениях.\n"
        "6. 🔴 Мошенник — Подтверждённые жалобы, нельзя доверять.\n"
    )
    await message.answer(text)


# =========================
# GROUP /check
# =========================

@router.message(Command("check"))
async def cmd_check(message: Message):
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в группах (по реплаю).")
        return
    if not message.reply_to_message:
        await message.answer("Сделайте /check ответом на сообщение пользователя, которого хотите проверить.")
        return

    db = load_db()
    target = message.reply_to_message.from_user
    user = get_user_record(db, target.id, target.username)
    save_db(db)
    await message.answer_photo(
        photo=status_photo_id(user["status"]),
        caption=build_status_caption(user),
    )


# =========================
# INLINE MODE
# =========================

@router.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.strip()
    db = load_db()
    if not query:
        content = InputTextMessageContent(
            "Введите @username или id123456789, чтобы проверить пользователя в @ZhorikBase."
        )
        result = InlineQueryResultArticle(
            id="empty",
            title="Поиск пользователя",
            description="Введите @username или id123456789",
            input_message_content=content,
        )
        await inline_query.answer([result], cache_time=1)
        return

    user = find_user_by_query(db, query)
    if user is None:
        txt = query
        username = None
        tg_id = None
        if txt.startswith("@"):
            username = txt[1:]
        elif txt.startswith("id") and txt[2:].isdigit():
            tg_id = int(txt[2:])
        elif txt.isdigit():
            tg_id = int(txt)

        user = {
            "id": tg_id or 0,
            "username": username or "не указан",
            "status": STATUS_UNKNOWN,
            "proof": None,
        }

    caption = build_status_caption(user)
    content = InputTextMessageContent(caption)
    result = InlineQueryResultArticle(
        id="user",
        title=f"Статус {user.get('username') or user.get('id')}",
        description=STATUS_TITLES.get(user["status"], "Неизвестный пользователь"),
        input_message_content=content,
    )
    await inline_query.answer([result], cache_time=1)


# =========================
# ADMIN / MODERATION
# =========================

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    db = load_db()
    users = db.get("users", {})
    counts = {s: 0 for s in STATUS_ORDER}
    for u in users.values():
        counts[u.get("status", STATUS_UNKNOWN)] = counts.get(u.get("status", STATUS_UNKNOWN), 0) + 1

    text_lines = [
        "📊 Статистика ZhorikBase:",
        f"Всего в базе: {len(users)}",
    ]
    for s in STATUS_ORDER:
        text_lines.append(f"{STATUS_TITLES[s]}: {counts.get(s, 0)}")
    text_lines.append("\nКоманды админа:")
    text_lines.append("/addmod id — добавить модератора")
    text_lines.append("/delmod id — убрать модератора")
    text_lines.append("/listmods — список модераторов")
    text_lines.append("/setstatus — изменить статус (для модеров тоже)")
    await message.answer("\n".join(text_lines))


@router.message(Command("addmod"))
async def cmd_addmod(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Использование: /addmod 123456789")
        return
    mid = int(args[1])
    db = load_db()
    if mid not in db["moderators"]:
        db["moderators"].append(mid)
        save_db(db)
    await message.answer(f"✅ Пользователь {mid} добавлен как модератор.")


@router.message(Command("delmod"))
async def cmd_delmod(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Использование: /delmod 123456789")
        return
    mid = int(args[1])
    db = load_db()
    if mid in db["moderators"]:
        db["moderators"].remove(mid)
        save_db(db)
        await message.answer(f"❌ Пользователь {mid} убран из модераторов.")
    else:
        await message.answer("Этот пользователь не модератор.")


def parse_status_code(text: str) -> Optional[str]:
    t = text.lower()
    mapping = {
        "team": STATUS_TEAM,
        "команда": STATUS_TEAM,
        "guarantor": STATUS_GUARANTOR,
        "гарант": STATUS_GUARANTOR,
        "verified": STATUS_VERIFIED,
        "проверенный": STATUS_VERIFIED,
        "unknown": STATUS_UNKNOWN,
        "неизвестный": STATUS_UNKNOWN,
        "doubt": STATUS_DOUBTFUL,
        "сомнительный": STATUS_DOUBTFUL,
        "scam": STATUS_SCAMMER,
        "scammer": STATUS_SCAMMER,
        "мошенник": STATUS_SCAMMER,
    }
    return mapping.get(t)


@router.message(Command("setstatus"))
async def cmd_setstatus(message: Message):
    db = load_db()
    if not is_moderator(message.from_user.id, db):
        return

    # формат:
    # /setstatus @user статус [пруф] | [комментарий]
    # минимум: /setstatus @user status
    args = message.text.split(maxsplit=3)
    if len(args) < 3:
        await message.answer("Использование: /setstatus @username статус [пруф] [комментарий]")
        return

    user_part = args[1]
    status_part = args[2]
    extra = args[3] if len(args) > 3 else ""

    status_code = parse_status_code(status_part)
    if not status_code:
        await message.answer("Неизвестный статус. Возможные: team, guarantor, verified, unknown, doubt, scam")
        return

    # цель: по ник/ID
    target_record = find_user_by_query(db, user_part)
    if target_record is None:
        # создаем новый
        username = None
        tg_id = None
        if user_part.startswith("@"):
            username = user_part[1:]
        elif user_part.startswith("id") and user_part[2:].isdigit():
            tg_id = int(user_part[2:])
        elif user_part.isdigit():
            tg_id = int(user_part)
        else:
            await message.answer("Не удалось разобрать пользователя. Используйте @username или id123.")
            return

        if tg_id is None:
            tg_id = 0

        target_record = {
            "id": tg_id,
            "username": username,
            "status": STATUS_UNKNOWN,
            "proof": None,
            "comment": None,
            "updated_by": None,
            "updated_at": None,
        }
        db["users"][str(tg_id)] = target_record

    # pruf / comment бөлшектеу - прост: всё extra как комментарий, если там ссылка есть, отправим как proof
    proof = None
    comment = None
    if extra:
        if "http://" in extra or "https://" in extra or "t.me" in extra:
            proof = extra
        else:
            comment = extra

    old_status = target_record.get("status", STATUS_UNKNOWN)
    target_record["status"] = status_code
    if proof:
        target_record["proof"] = proof
    if comment:
        target_record["comment"] = comment
    target_record["updated_by"] = message.from_user.id
    target_record["updated_at"] = datetime.utcnow().isoformat()

    save_db(db)

    entry = log_action(
        moderator_id=message.from_user.id,
        target_id=target_record["id"],
        old_status=old_status,
        new_status=status_code,
        proof=proof,
        comment=comment,
    )

    await message.answer(
        f"✅ Статус пользователя обновлён: {STATUS_TITLES.get(status_code)}\n"
        f"ID: {target_record['id']} | @{target_record.get('username')}"
    )

    # уведомление админам
    text = (
        "📢 Действие модератора:\n"
        f"Модератор: <code>{message.from_user.id}</code> (@{message.from_user.username})\n"
        f"Цель: <code>{target_record['id']}</code> (@{target_record.get('username')})\n"
        f"Статус: {STATUS_TITLES.get(old_status)} → {STATUS_TITLES.get(status_code)}\n"
    )
    if proof:
        text += f"Пруф: {proof}\n"
    if comment:
        text += f"Комментарий: {comment}\n"
    text += f"Время: {entry['time']}"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


@router.message(Command("listmods"))
async def cmd_listmods(message: Message):
    if not is_admin(message.from_user.id):
        return
    db = load_db()
    mods = db.get("moderators", [])
    if not mods:
        await message.answer("Модераторов пока нет.")
        return
    text = "Список модераторов:\n" + "\n".join([str(m) for m in mods])
    await message.answer(text)


# =========================
# ENTRYPOINT
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
