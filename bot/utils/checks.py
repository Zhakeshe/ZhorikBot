from typing import List, Optional, Tuple
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import User

SUB_CHANNELS = ["@ZhorikBase", "@ZhorikBaseProofs"]


def parse_search_query(text: str) -> Optional[str]:
    cleaned = text.strip()
    if cleaned.startswith("@"):  # username
        username = cleaned[1:]
        if username:
            return username
    if cleaned.lower().startswith("id") and cleaned[2:].isdigit():
        return cleaned[2:]
    if cleaned.isdigit():
        return cleaned
    return None


async def ensure_subscription(bot: Bot, user: User) -> Tuple[bool, List[str]]:
    missing: List[str] = []
    for channel in SUB_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user.id)
            if member.status in {"left", "kicked"}:
                missing.append(channel)
        except TelegramForbiddenError:
            missing.append(channel)
    return (not missing, missing)
