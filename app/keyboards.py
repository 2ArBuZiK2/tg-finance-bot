from collections import Counter
from collections.abc import Iterable

from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Category, Transaction

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить расход"),
         KeyboardButton(text="Добавить доход")],
        [KeyboardButton(text="История"),
         KeyboardButton(text="Статистика")],
        [KeyboardButton(text="Управление категориями")],
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


def categories_management_keyboard(
    items: list[tuple[Category, int]],
    missing_defaults: int,
) -> InlineKeyboardMarkup:
    """Список категорий: кнопка удаления на каждую + действия."""
    builder = InlineKeyboardBuilder()

    # Если имя встречается и в расходах, и в доходах, подписываем тип,
    # иначе две кнопки «🗑 Другое» неразличимы.
    duplicates = {
        name for name, count in Counter(category.name for category, _ in items).items()
        if count > 1
    }

    for category, _ in items:
        label = f"🗑 {category.name}"
        if category.name in duplicates:
            label += " (расход)" if category.type == "expense" else " (доход)"
        builder.button(text=label, callback_data=f"delcat_{category.id}")

    builder.adjust(2)

    if missing_defaults:
        builder.row(
            InlineKeyboardButton(
                text=f"➕ Базовые категории ({missing_defaults})",
                callback_data="cat_defaults",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить категорию", callback_data="cat_add")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ В меню", callback_data="close")
    )
    return builder.as_markup()


def confirm_delete_category_keyboard(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить",
                    callback_data=f"delcat_ok_{category_id}",
                ),
                InlineKeyboardButton(text="↩️ Назад", callback_data="cat_manage"),
            ]
        ]
    )


def history_keyboard(
    items: list[tuple[Transaction, Category]],
    offset: int,
    total: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for index, (transaction, _) in enumerate(items, start=offset + 1):
        builder.button(
            text=f"🗑 {index}",
            callback_data=f"deltx_{transaction.id}_{offset}",
        )
    builder.adjust(5)

    navigation = []
    if offset > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ Новее",
                callback_data=f"hist_{max(0, offset - page_size)}",
            )
        )
    if offset + page_size < total:
        navigation.append(
            InlineKeyboardButton(
                text=f"Ещё {page_size} ➡️",
                callback_data=f"hist_{offset + page_size}",
            )
        )
    if navigation:
        builder.row(*navigation)

    builder.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="close"))
    return builder.as_markup()


def confirm_delete_transaction_keyboard(
    transaction_id: int,
    offset: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить",
                    callback_data=f"deltx_ok_{transaction_id}_{offset}",
                ),
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=f"hist_{offset}",
                ),
            ]
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
