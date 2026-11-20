from collections.abc import Iterable

from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Category

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить расход"),
         KeyboardButton(text="Добавить доход")],
        [KeyboardButton(text="Управление категориями"),
         KeyboardButton(text="Статистика")],
    ],
    resize_keyboard=True,
)


def categories_keyboard(categories: Iterable[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.button(text=category.name, callback_data=f"categ_{category.id}")

    builder.adjust(2)
    # Отмена всегда отдельной строкой, чтобы не смешиваться с категориями.
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def cancel_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


def get_type_category() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text="Расход", callback_data="type_expense")
    builder.button(text="Доход", callback_data="type_income")
    builder.adjust(2)
    return builder.as_markup()


def get_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    periods = [
        ("Сегодня", "period_today"),
        ("7 дней", "period_week"),
        ("Этот месяц", "period_month"),
        ("Всё время", "period_all"),
    ]
    for text, callback_data in periods:
        builder.button(text=text, callback_data=callback_data)

    builder.adjust(2)
    return builder.as_markup()
