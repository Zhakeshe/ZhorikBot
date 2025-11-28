import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

DB_PATH = Path("database.json")
LOG_FILE_PATH = Path("logs.json")

DEFAULT_STATUSES: Dict[str, Dict[str, str]] = {
    "team": {
        "title": "⚙ Команда бота",
        "description": "Участник команды ZhorikBase.",
        "photo": "https://i.imgur.com/Qz9s5rM.png",
    },
    "guarantor": {
        "title": "🛡 Гарант",
        "description": "Рекомендованный гарант.",
        "photo": "https://i.imgur.com/ev7tnBe.png",
    },
    "verified": {
        "title": "🟢 Проверенный",
        "description": "Пользователь с подтвержденной репутацией.",
        "photo": "https://i.imgur.com/6p3ibEd.png",
    },
    "unknown": {
        "title": "❓ Неизвестный",
        "description": "Нет данных — будьте осторожны.",
        "photo": "https://i.imgur.com/4rKBePk.png",
    },
    "doubtful": {
        "title": "🟠 Сомнительный",
        "description": "Есть сомнения в надежности.",
        "photo": "https://i.imgur.com/VfU8XDW.png",
    },
    "scammer": {
        "title": "🔴 Мошенник",
        "description": "Зафиксированы жалобы на мошенничество.",
        "photo": "https://i.imgur.com/5t49PxD.png",
    },
}

DEFAULT_DB: Dict[str, object] = {
    "users": {
        "75874120": {
            "id": 75874120,
            "username": "aqrxrx",
            "status": "scammer",
            "proof": "https://t.me/link",
            "comment": "много жалоб",
            "updated_by": 123456,
            "updated_at": "2025-01-01T10:00:00",
        }
    },
    "statuses": DEFAULT_STATUSES,
    "moderators": [123],
    "logs": [
        {
            "time": "2025-01-01T10:00:00",
            "moderator_id": 123,
            "target_id": 75874120,
            "old_status": "unknown",
            "new_status": "scammer",
            "proof": "url",
            "comment": "много жалоб",
        }
    ],
}


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_database() -> None:
    if not DB_PATH.exists():
        _write_json(DB_PATH, DEFAULT_DB)
    else:
        data = read_db()
        changed = False
        if "statuses" not in data:
            data["statuses"] = DEFAULT_STATUSES
            changed = True
        for code, payload in DEFAULT_STATUSES.items():
            if code not in data["statuses"]:
                data["statuses"][code] = payload
                changed = True
        if "users" not in data:
            data["users"] = {}
            changed = True
        if "moderators" not in data:
            data["moderators"] = []
            changed = True
        if "logs" not in data:
            data["logs"] = []
            changed = True
        if changed:
            write_db(data)
    if not LOG_FILE_PATH.exists():
        _write_json(LOG_FILE_PATH, [])


def read_db() -> Dict[str, object]:
    if not DB_PATH.exists():
        ensure_database()
    with DB_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_db(data: Dict[str, object]) -> None:
    _write_json(DB_PATH, data)


def get_statuses() -> Dict[str, Dict[str, str]]:
    return read_db().get("statuses", {})


def save_status(code: str, title: str, description: str, photo: str) -> None:
    data = read_db()
    statuses = data.setdefault("statuses", {})
    statuses[code] = {"title": title, "description": description, "photo": photo}
    write_db(data)


def delete_status(code: str) -> bool:
    data = read_db()
    users = data.get("users", {})
    if any(user.get("status") == code for user in users.values()):
        return False
    statuses = data.setdefault("statuses", {})
    if code in statuses:
        statuses.pop(code)
        write_db(data)
        return True
    return False


def update_status(code: str, title: Optional[str] = None, description: Optional[str] = None, photo: Optional[str] = None) -> bool:
    data = read_db()
    statuses = data.setdefault("statuses", {})
    if code not in statuses:
        return False
    current = statuses[code]
    if title:
        current["title"] = title
    if description:
        current["description"] = description
    if photo:
        current["photo"] = photo
    statuses[code] = current
    write_db(data)
    return True


def get_user(identifier: str) -> Optional[Dict[str, object]]:
    data = read_db()
    users = data.get("users", {})
    if identifier in users:
        return users[identifier]
    for user in users.values():
        if user.get("username", "").lower() == identifier.lower():
            return user
    return None


def upsert_user(user_id: int, username: Optional[str], status: str, proof: Optional[str], comment: Optional[str], updated_by: int) -> Dict[str, object]:
    data = read_db()
    users = data.setdefault("users", {})
    key = str(user_id)
    user = users.get(key, {})
    old_status = user.get("status", "unknown")
    user.update(
        {
            "id": user_id,
            "username": username or user.get("username"),
            "status": status,
            "proof": proof or "",
            "comment": comment or "",
            "updated_by": updated_by,
            "updated_at": datetime.utcnow().isoformat(),
        }
    )
    users[key] = user
    data["users"] = users
    write_db(data)
    return {"old_status": old_status, "user": user}


def list_users_by_status(status_code: str) -> List[Dict[str, object]]:
    data = read_db()
    users = data.get("users", {})
    return [user for user in users.values() if user.get("status") == status_code]


def stats_by_status() -> Dict[str, int]:
    data = read_db()
    users = data.get("users", {})
    counts: Dict[str, int] = {}
    for user in users.values():
        status = user.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def get_moderators() -> List[int]:
    data = read_db()
    return data.get("moderators", [])


def add_moderator(user_id: int) -> None:
    data = read_db()
    mods: List[int] = data.setdefault("moderators", [])
    if user_id not in mods:
        mods.append(user_id)
        data["moderators"] = mods
        write_db(data)


def remove_moderator(user_id: int) -> bool:
    data = read_db()
    mods: List[int] = data.setdefault("moderators", [])
    if user_id in mods:
        mods.remove(user_id)
        data["moderators"] = mods
        write_db(data)
        return True
    return False


def get_log_entries() -> List[Dict[str, object]]:
    data = read_db()
    return data.get("logs", [])


def append_log(entry: Dict[str, object]) -> None:
    data = read_db()
    logs: List[Dict[str, object]] = data.setdefault("logs", [])
    logs.append(entry)
    data["logs"] = logs
    write_db(data)
    history: List[object] = []
    if LOG_FILE_PATH.exists():
        try:
            history = json.loads(LOG_FILE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    _write_json(LOG_FILE_PATH, history)


def ensure_status_exists(code: str) -> bool:
    return code in get_statuses()


def resolve_user(query: str) -> Tuple[str, Optional[Dict[str, object]]]:
    if query.startswith("@"):  # username
        username = query[1:]
        user = get_user(username)
        return (username, user)
    cleaned = query
    if query.lower().startswith("id"):
        cleaned = query[2:]
    if cleaned.isdigit():
        user = get_user(cleaned)
        return (cleaned, user)
    return (query, None)
