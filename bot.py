"""
Neuro Learning Bot — aiogram 3.x
Запуск: BOT_TOKEN=xxx python bot.py
"""
import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database import (
    init_db,
    get_user,
    register_user,
    set_reading_flag,
    advance_topic,
    reset_user,
    get_completed_count,
    get_all_user_ids,
)
from keyboards import (
    read_keyboard,
    next_part_keyboard,
    progress_keyboard,
    confirm_reset_keyboard,
)
from topics import TOPICS, ALL_TOPIC_TITLES

# ─── Логирование ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Конфиг ─────────────────────────────────────────────────────
config = load_config()
MAX_LEN = config.MAX_MSG_LEN

# ─── Роутер ─────────────────────────────────────────────────────
router = Router()


# ════════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ════════════════════════════════════════════════════════════════

def split_text(text: str, limit: int = MAX_LEN) -> list[str]:
    """
    Разбивает длинный MarkdownV2-текст на части ≤ limit символов.
    Старается резать по двойному переводу строки, не ломая абзацы.
    """
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        # Ищем последний \n\n в пределах лимита
        cut = text.rfind("\n\n", 0, limit)
        if cut == -1:
            # Нет двойного переноса — режем по одиночному
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            # Крайний случай — режем жёстко
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts


async def send_topic(bot: Bot, user_id: int, topic_index: int) -> None:
    """
    Отправляет тему по частям. Под последней частью — кнопка «Я прочитал».
    """
    if topic_index >= len(TOPICS):
        await bot.send_message(
            user_id,
            "🎓 *Вы прошли все доступные темы\\!* Новые темы скоро появятся\\.",
            parse_mode="MarkdownV2",
        )
        return

    topic = TOPICS[topic_index]
    parts = split_text(topic["text"])
    total = len(parts)

    await set_reading_flag(user_id, 1)

    for i, part in enumerate(parts):
        is_last = i == total - 1
        try:
            if is_last:
                await bot.send_message(
                    user_id,
                    part,
                    parse_mode="MarkdownV2",
                    reply_markup=read_keyboard(),
                )
            elif i < total - 1:
                await bot.send_message(
                    user_id,
                    part,
                    parse_mode="MarkdownV2",
                    reply_markup=next_part_keyboard(i + 1, total),
                )
            # Небольшая задержка между частями, чтобы не триггерить rate limit
            if not is_last:
                await asyncio.sleep(0.5)
        except TelegramForbiddenError:
            logger.warning("User %s blocked the bot", user_id)
            return
        except TelegramBadRequest as e:
            logger.error("Bad request for user %s: %s", user_id, e)
            return


# ════════════════════════════════════════════════════════════════
# КОМАНДЫ
# ════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username or str(user_id)

    await register_user(user_id, username)
    user = await get_user(user_id)

    if user and user["current_topic"] > 0:
        await message.answer(
            f"С возвращением\\! Вы на теме *{user['current_topic'] + 1}*\\.\n"
            "Используйте /next чтобы продолжить или /progress для статистики\\.",
            parse_mode="MarkdownV2",
        )
    else:
        await message.answer(
            "👋 *Добро пожаловать в нейрокурс\\!*\n\n"
            "Каждый день в *19:00* вы будете получать одну тему для глубокого изучения\\.\n"
            "Каждая тема рассчитана на *10 минут вдумчивого чтения*\\.\n\n"
            "📚 После прочтения нажмите кнопку «Я прочитал» — "
            "только тогда откроется следующая тема\\.\n\n"
            "Команды:\n"
            "/next — получить текущую тему\n"
            "/progress — ваша статистика\n"
            "/reset — сбросить прогресс\n\n"
            "Начнём прямо сейчас?",
            parse_mode="MarkdownV2",
        )
        await send_topic(message.bot, user_id, 0)


@router.message(Command("next"))
async def cmd_next(message: Message) -> None:
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await register_user(user_id, message.from_user.username or str(user_id))
        user = await get_user(user_id)

    if user["reading"] == 1:
        await message.answer(
            "📖 Вы ещё не завершили текущую тему\\.\n"
            "Дочитайте до конца и нажмите кнопку *«Я прочитал»*\\.",
            parse_mode="MarkdownV2",
        )
        return

    topic_index = user["current_topic"]
    if topic_index >= len(TOPICS):
        await message.answer(
            "🎓 Вы прошли все доступные темы\\! Отличная работа\\.",
            parse_mode="MarkdownV2",
        )
        return

    await send_topic(message.bot, user_id, topic_index)


@router.message(Command("progress"))
async def cmd_progress(message: Message) -> None:
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await message.answer("Сначала запустите бота командой /start\\.", parse_mode="MarkdownV2")
        return

    completed = await get_completed_count(user_id)
    current = user["current_topic"]
    total = len(ALL_TOPIC_TITLES)
    percent = round(completed / total * 100)

    progress_bar = "▓" * (completed // 5) + "░" * ((total - completed) // 5)

    lines = [f"📊 *Ваш прогресс:* {completed}/{total} тем \\({percent}%\\)\n"]
    lines.append(f"`{progress_bar}`\n")

    if current < total:
        lines.append(f"Текущая тема: *{current + 1}\\. {escape_md(ALL_TOPIC_TITLES[current])}*\n")

    lines.append("\n*Пройденные темы:*")
    for i in range(min(completed, total)):
        lines.append(f"✅ {i + 1}\\. {escape_md(ALL_TOPIC_TITLES[i])}")

    if completed < total:
        lines.append(f"\n*Осталось:* {total - completed} тем")

    await message.answer(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        reply_markup=progress_keyboard(),
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    await message.answer(
        "⚠️ Вы уверены, что хотите *сбросить весь прогресс*?\n"
        "Это действие необратимо\\.",
        parse_mode="MarkdownV2",
        reply_markup=confirm_reset_keyboard(),
    )


# ════════════════════════════════════════════════════════════════
# CALLBACK HANDLERS
# ════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "mark_read")
async def cb_mark_read(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not user:
        await callback.answer("Сначала запустите /start", show_alert=True)
        return

    new_index = await advance_topic(user_id)
    completed = await get_completed_count(user_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Тема засчитана!")

    total = len(TOPICS)
    if new_index >= total:
        await callback.message.answer(
            f"🏆 *Поздравляем\\!* Вы завершили все {total} тем курса\\!\n\n"
            "Это редкое достижение\\. Ваш мозг сегодня значительно богаче, "
            "чем был в начале\\.",
            parse_mode="MarkdownV2",
        )
    else:
        next_title = escape_md(ALL_TOPIC_TITLES[new_index])
        await callback.message.answer(
            f"✅ *Тема {completed} завершена\\!*\n\n"
            f"Следующая тема: *{new_index + 1}\\. {next_title}*\n"
            f"Она придёт в 19:00 или нажмите /next прямо сейчас\\.",
            parse_mode="MarkdownV2",
        )


@router.callback_query(F.data.startswith("part:"))
async def cb_next_part(callback: CallbackQuery) -> None:
    """
    Обрабатывает кнопки перехода между частями (Part 1, Part 2...).
    Часть уже отправлена — просто убираем кнопку, пользователь видит следующую часть.
    """
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data == "next_topic")
async def cb_next_topic(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if user and user["reading"] == 1:
        await callback.answer(
            "Сначала дочитайте текущую тему и нажмите «Я прочитал»",
            show_alert=True,
        )
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    topic_index = user["current_topic"] if user else 0
    await send_topic(callback.bot, user_id, topic_index)


@router.callback_query(F.data == "confirm_reset")
async def cb_confirm_reset(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "⚠️ *Точно сбросить прогресс?*",
        parse_mode="MarkdownV2",
        reply_markup=confirm_reset_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "do_reset")
async def cb_do_reset(callback: CallbackQuery) -> None:
    await reset_user(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Прогресс сброшен")
    await callback.message.answer(
        "🔄 Прогресс сброшен\\. Начинаем с первой темы\\!\n"
        "Нажмите /next или дождитесь 19:00\\.",
        parse_mode="MarkdownV2",
    )


@router.callback_query(F.data == "cancel_reset")
async def cb_cancel_reset(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено")
    await callback.message.answer("Сброс отменён\\. Продолжаем учиться\\! 💪", parse_mode="MarkdownV2")


# ════════════════════════════════════════════════════════════════
# SCHEDULER: РАССЫЛКА В 19:00
# ════════════════════════════════════════════════════════════════

async def daily_broadcast(bot: Bot) -> None:
    logger.info("Starting daily broadcast")
    user_ids = await get_all_user_ids()

    for user_id in user_ids:
        user = await get_user(user_id)
        if not user:
            continue
        if user["reading"] == 1:
            # Пользователь ещё не закончил предыдущую тему — не отправляем
            logger.info("User %s still reading, skip", user_id)
            continue
        if user["current_topic"] >= len(TOPICS):
            continue
        try:
            await send_topic(bot, user_id, user["current_topic"])
            await asyncio.sleep(0.05)  # защита от flood
        except TelegramForbiddenError:
            logger.warning("User %s blocked the bot, skip broadcast", user_id)
        except Exception as e:
            logger.error("Broadcast error for user %s: %s", user_id, e)

    logger.info("Daily broadcast done for %d users", len(user_ids))


# ════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ════════════════════════════════════════════════════════════════

def escape_md(text: str) -> str:
    """Экранирует спецсимволы MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(r"([" + re.escape(escape_chars) + r"])", r"\\\1", text)


# ════════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ════════════════════════════════════════════════════════════════

async def main() -> None:
    await init_db(config.DB_PATH)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        daily_broadcast,
        trigger="cron",
        hour=config.SEND_HOUR,
        minute=config.SEND_MINUTE,
        args=[bot],
    )
    scheduler.start()
    logger.info(
        "Scheduler started: daily broadcast at %02d:%02d",
        config.SEND_HOUR,
        config.SEND_MINUTE,
    )

    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
