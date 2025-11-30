from typing import Dict, Optional

from .db import get_statuses

FOOTER = (
    "Группа: @ZhorikBase\n"
    "Канал: @ZhorikBaseProofs\n"
    "Личка: @ZhorikBaseRobot"
)


def status_photo(code: str) -> str:
    statuses = get_statuses()
    default_photo = statuses.get("unknown", {}).get("photo", "")
    return statuses.get(code, {}).get("photo", default_photo)


def status_title(code: str) -> str:
    statuses = get_statuses()
    return statuses.get(code, {}).get("title", "❓ Неизвестный")


def status_description(code: str) -> str:
    statuses = get_statuses()
    return statuses.get(code, {}).get("description", "Нет данных — будьте осторожны.")


def format_status_line(user: Dict[str, object]) -> str:
    status_code = user.get("status", "unknown")
    username = user.get("username")
    username_block = f"@{username}" if username else "без ника"
    return f"{status_title(status_code)} | {username_block} | id {user.get('id')}"


def render_profile(user: Dict[str, object]) -> str:
    status_code = user.get("status", "unknown")
    header_username = f"@{user.get('username')}" if user.get("username") else "без ника"
    proof = user.get("proof") or "—"
    comment = user.get("comment") or "—"
    body = (
        f"🔺 {header_username} | id {user.get('id')}\n\n"
        f"{status_title(status_code)}\n"
        f"{status_description(status_code)}\n\n"
        f"Пруф: {proof}\n"
        f"Комментарий: {comment}\n\n"
        f"{FOOTER}"
    )
    return body


def format_status_text(user: Optional[Dict[str, object]], query: str) -> str:
    if not user:
        status_code = "unknown"
        status_line = f"❓ Неизвестный | {query}"
        proof = "—"
        comment = "—"
    else:
        status_code = user.get("status", "unknown")
        username = f"@{user.get('username')}" if user.get("username") else query
        status_line = f"{status_title(status_code)} | {username} | id {user.get('id')}"
        proof = user.get("proof") or "—"
        comment = user.get("comment") or "—"
    return (
        f"{status_line}\n"
        f"{status_description(status_code)}\n\n"
        f"Пруф: {proof}\n"
        f"Комментарий: {comment}\n\n"
        f"{FOOTER}"
    )
