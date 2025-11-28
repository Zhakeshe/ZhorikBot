from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message

from bot.keyboards.subscription import subscription_keyboard
from bot.utils.checks import ensure_subscription, parse_search_query
from bot.utils.db import resolve_user
from bot.utils.status import format_status_text, status_photo

router = Router()


async def respond_with_status(message: Message, query: str) -> None:
    subscribed, _ = await ensure_subscription(message.bot, message.from_user)
    if not subscribed:
        await message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    normalized, user = resolve_user(query)
    caption = format_status_text(user, normalized)
    await message.answer_photo(photo=status_photo(user.get("status", "unknown") if user else "unknown"), caption=caption)


@router.message(Command("search"))
async def handle_search(message: Message, command: CommandObject) -> None:
    if command.args:
        query = command.args.strip()
        await respond_with_status(message, query)
    else:
        await message.answer("Укажите ID или username для поиска: /search id123 или /search @name")


# Non-blocking free-text handler so command messages continue to other routers
@router.message(F.text, flags={"block": False})
async def handle_free_text(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        return
    query = parse_search_query(message.text or "")
    if not query:
        return
    await respond_with_status(message, query)


@router.callback_query(F.data == "menu_search")
async def handle_menu_search(call: CallbackQuery) -> None:
    subscribed, _ = await ensure_subscription(call.bot, call.from_user)
    if not subscribed:
        await call.message.answer(
            "Для работы бота необходима подписка на каналы.",
            reply_markup=subscription_keyboard(),
        )
        return
    await call.message.answer("Отправьте @username или id123456 для проверки статуса.")


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery) -> None:
    query_text = inline_query.query.strip()
    if not query_text:
        await inline_query.answer([], cache_time=1)
        return
    parsed = parse_search_query(query_text)
    if not parsed:
        await inline_query.answer([], cache_time=1)
        return
    normalized, user = resolve_user(parsed)
    text = format_status_text(user, normalized)
    result = InlineQueryResultArticle(
        id="status",
        title="Результат поиска",
        description=text.replace("\n", " ")[:100],
        input_message_content=InputTextMessageContent(message_text=text),
        thumb_url=status_photo(user.get("status", "unknown") if user else "unknown"),
    )
    await inline_query.answer([result], cache_time=1, is_personal=True)


@router.message(Command("check"))
async def handle_check(message: Message, command: CommandObject) -> None:
    query = None
    if message.reply_to_message:
        reply_user = message.reply_to_message.from_user
        if reply_user:
            query = str(reply_user.id)
    if not query and command.args:
        query = command.args.strip()
    if not query:
        await message.answer("Используйте /check @user или /check id123456789.")
        return
    await respond_with_status(message, query)
