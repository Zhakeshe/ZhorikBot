import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import admin, help, lists, profile, search, start
from bot.utils.db import ensure_database


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ensure_database()
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(help.router)
    dp.include_router(profile.router)
    dp.include_router(lists.router)
    dp.include_router(search.router)
    dp.include_router(admin.router)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
