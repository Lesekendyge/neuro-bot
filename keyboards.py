from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def read_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Я прочитал' под последней частью темы."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="✅ Я прочитал — следующая тема",
            callback_data="mark_read",
        )
    )
    return builder.as_markup()


def next_part_keyboard(part: int, total: int) -> InlineKeyboardMarkup:
    """Кнопка перехода к следующей части длинного текста."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=f"▶️ Часть {part + 1} / {total}",
            callback_data=f"part:{part}",
        )
    )
    return builder.as_markup()


def progress_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="📚 Следующая тема", callback_data="next_topic"),
        InlineKeyboardButton(text="🔄 Сбросить прогресс", callback_data="confirm_reset"),
    )
    builder.adjust(1)
    return builder.as_markup()


def confirm_reset_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="⚠️ Да, сбросить", callback_data="do_reset"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reset"),
    )
    builder.adjust(2)
    return builder.as_markup()
