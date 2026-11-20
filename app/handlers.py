from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import app.database.requests as rq
import app.keyboards as kb
from app.database.models import Category
from app.states import AddCategory, AddTransaction
from app.utils import MAX_AMOUNT, MAX_CATEGORY_NAME, format_money, parse_amount

router = Router()

EXPENSE = "expense"
INCOME = "income"

HISTORY_PAGE = 10

PERIOD_NAMES = {
    "today": "сегодня",
    "week": "последние 7 дней",
    "month": "этот месяц",
    "all": "всё время",
}

TYPE_NAMES = {
    EXPENSE: "Расход",
    INCOME: "Доход",
}


async def _remove_markup(message: Message | None) -> None:
    """Убирает inline-кнопки у сообщения, чтобы ими нельзя было нажать дважды."""
    if message is None:
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # Сообщение слишком старое или клавиатура уже удалена.
        pass


async def _edit_message(
    message: Message | None,
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    """Перерисовывает экран на месте, а если нельзя — отправляет новый."""
    if message is None:
        return
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as error:
        if "message is not modified" in str(error):
            return
        await message.answer(text, reply_markup=markup)


def _extract_id(data: str | None, prefix: str) -> int | None:
    if not data:
        return None
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None


def _operations_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "операция"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "операции"
    return "операций"


async def _categories_view(tg_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = await rq.get_categories_with_counts(tg_id)
    missing_defaults = rq.missing_default_count([category for category, _ in items])

    if not items:
        text = "🗂 Категорий пока нет. Добавьте первую — без неё нельзя вносить операции."
    else:
        lines = ["🗂 Категории", ""]
        for category_type, title in ((EXPENSE, "Расходы"), (INCOME, "Доходы")):
            group = [
                (category, count)
                for category, count in items
                if category.type == category_type
            ]
            if not group:
                continue
            lines.append(f"{title} ({len(group)}):")
            for category, count in group:
                suffix = f" — {count} {_operations_word(count)}" if count else ""
                lines.append(f"• {category.name}{suffix}")
            lines.append("")
        lines.append("Нажмите 🗑, чтобы удалить категорию.")
        text = "\n".join(lines).strip()

    return text, kb.categories_management_keyboard(items, missing_defaults)


def _parse_tx_callback(data: str | None, prefix: str) -> tuple[int, int] | None:
    """Разбирает callback вида deltx_ok_42_10 → (42, 10)."""
    if not data:
        return None
    transaction_part, _, offset_part = data.removeprefix(prefix).partition("_")
    try:
        return int(transaction_part), int(offset_part or 0)
    except ValueError:
        return None


def _transaction_line(index: int, transaction, category: Category) -> str:
    sign = "−" if transaction.type == EXPENSE else "+"
    return (
        f"{index}. {transaction.date:%d.%m.%Y} · {category.name} · "
        f"{sign}{format_money(transaction.amount)} ₽"
    )


async def _history_view(tg_id: int, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    total = await rq.count_transactions(tg_id)

    if total == 0:
        return (
            "🧾 Операций пока нет. Добавьте расход или доход — они появятся здесь.",
            kb.history_keyboard([], 0, 0, HISTORY_PAGE),
        )

    last_page_offset = ((total - 1) // HISTORY_PAGE) * HISTORY_PAGE
    offset = max(0, min(offset, last_page_offset))

    items = await rq.get_transactions(tg_id, HISTORY_PAGE, offset)

    lines = [f"🧾 Операции: {total}", ""]
    for index, (transaction, category) in enumerate(items, start=offset + 1):
        lines.append(_transaction_line(index, transaction, category))
    lines += ["", "Нажмите 🗑 под номером, чтобы удалить операцию."]

    return "\n".join(lines), kb.history_keyboard(items, offset, total, HISTORY_PAGE)


# --- Команды и меню ---------------------------------------------------------
# Обработчики меню намеренно объявлены до обработчиков состояний: кнопки
# нижней клавиатуры должны работать даже во время ввода суммы или названия.


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    _, created = await rq.ensure_user(message.from_user.id)

    text = "Привет! Я помогу вести учёт доходов и расходов."
    if created:
        text += (
            "\n\nЯ уже создал базовые категории — можно сразу добавлять"
            " траты. Свои категории добавляются в «Управление категориями»."
        )
    else:
        text += "\n\nВыберите действие в меню ниже."

    await message.answer(text, reply_markup=kb.main)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    await state.clear()

    if current_state is None:
        await message.answer("Нечего отменять. Выберите действие в меню:", reply_markup=kb.main)
    else:
        await message.answer("Действие отменено.", reply_markup=kb.main)


@router.message(F.text == "Добавить расход")
async def add_expense(message: Message, state: FSMContext):
    await _start_transaction(message, state, EXPENSE)


@router.message(F.text == "Добавить доход")
async def add_income(message: Message, state: FSMContext):
    await _start_transaction(message, state, INCOME)


@router.message(F.text == "Управление категориями")
async def manage_categories(message: Message, state: FSMContext):
    await state.clear()
    text, markup = await _categories_view(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.message(F.text == "Статистика")
async def stats(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите период:", reply_markup=kb.get_period_keyboard())


@router.message(F.text == "История")
async def history(message: Message, state: FSMContext):
    await state.clear()
    text, markup = await _history_view(message.from_user.id, 0)
    await message.answer(text, reply_markup=markup)


async def _start_transaction(message: Message, state: FSMContext, category_type: str) -> None:
    categories = await rq.get_categories_by_user_and_type(
        message.from_user.id, category_type
    )

    await state.clear()

    if not categories:
        await message.answer(
            f"У вас пока нет категорий ({'расходов' if category_type == EXPENSE else 'доходов'})."
            " Создайте их в «Управление категориями».",
            reply_markup=kb.main,
        )
        return

    await state.set_state(AddTransaction.choosing_category)
    await state.update_data(transaction_type=category_type)
    await message.answer(
        f"{TYPE_NAMES[category_type]}: выберите категорию",
        reply_markup=kb.categories_keyboard(categories),
    )


# --- Сценарий добавления транзакции ----------------------------------------


@router.callback_query(F.data.startswith("categ_"), AddTransaction.choosing_category)
async def category_selection(callback: CallbackQuery, state: FSMContext):
    try:
        category_id = int(callback.data.split("_", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    data = await state.get_data()
    transaction_type = data.get("transaction_type")

    category = await rq.get_category(callback.from_user.id, category_id)
    if not category or category.type != transaction_type:
        await state.clear()
        await _remove_markup(callback.message)
        await callback.answer("Категория не найдена, начните заново", show_alert=True)
        return

    await state.update_data(category_id=category.id, category_name=category.name)
    await state.set_state(AddTransaction.enter_amount)

    await _remove_markup(callback.message)
    await callback.answer()
    await callback.message.answer(
        f"Категория: {category.name}\n"
        "Введите сумму, например 1250,50:",
        reply_markup=kb.cancel_inline(),
    )


@router.message(AddTransaction.enter_amount)
async def enter_amount(message: Message, state: FSMContext):
    amount = parse_amount(message.text)

    if amount is None or amount <= 0:
        await message.answer("Введите положительное число, например 1250,50:")
        return

    if amount > MAX_AMOUNT:
        await message.answer(
            f"Слишком большая сумма. Максимум — {format_money(MAX_AMOUNT)} ₽."
        )
        return

    data = await state.get_data()
    category_id = data.get("category_id")
    category_name = data.get("category_name")
    transaction_type = data.get("transaction_type")

    if category_id is None or transaction_type is None:
        await state.clear()
        await message.answer(
            "Что-то пошло не так. Начните заново из меню.",
            reply_markup=kb.main,
        )
        return

    result = await rq.add_transaction(
        tg_id=message.from_user.id,
        category_id=category_id,
        amount=amount,
        category_type=transaction_type,
    )

    await state.clear()

    if result:
        await message.answer(
            f"✅ {TYPE_NAMES[transaction_type]}: {format_money(amount)} ₽\n"
            f"Категория: {category_name}",
            reply_markup=kb.main,
        )
    else:
        await message.answer(
            "Не удалось сохранить транзакцию. Проверьте категорию и попробуйте снова.",
            reply_markup=kb.main,
        )


# --- Сценарий добавления категории -----------------------------------------


@router.message(AddCategory.name)
async def add_category_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()

    if not name or len(name) > MAX_CATEGORY_NAME:
        await message.answer(
            f"Название должно быть от 1 до {MAX_CATEGORY_NAME} символов. Попробуйте снова:"
        )
        return

    await state.update_data(category_name=name)
    await state.set_state(AddCategory.type)
    await message.answer(
        f"Категория «{name}». Выберите тип:",
        reply_markup=kb.get_type_category(),
    )


@router.callback_query(F.data.startswith("type_"), AddCategory.type)
async def category_type(callback: CallbackQuery, state: FSMContext):
    selected_type = callback.data.split("_", 1)[1]

    if selected_type not in (EXPENSE, INCOME):
        await callback.answer("Неизвестный тип категории", show_alert=True)
        return

    data = await state.get_data()
    name = data.get("category_name")

    if not name:
        await state.clear()
        await _remove_markup(callback.message)
        await callback.answer("Сессия устарела, начните заново", show_alert=True)
        return

    result = await rq.add_category(
        tg_id=callback.from_user.id,
        name=name,
        category_type=selected_type,
    )

    if result is None:
        await callback.answer(
            f"В списке «{'Расходы' if selected_type == EXPENSE else 'Доходы'}» "
            f"уже есть категория «{name}»",
            show_alert=True,
        )
        return

    await state.clear()
    text, markup = await _categories_view(callback.from_user.id)
    await _edit_message(callback.message, text, markup)
    await callback.answer("Категория добавлена")


# --- Управление категориями -------------------------------------------------


@router.callback_query(F.data == "cat_manage")
async def show_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await _categories_view(callback.from_user.id)
    await _edit_message(callback.message, text, markup)
    await callback.answer()


@router.callback_query(F.data == "cat_add")
async def start_add_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AddCategory.name)
    await _edit_message(
        callback.message,
        f"Введите название новой категории (до {MAX_CATEGORY_NAME} символов):",
        kb.cancel_inline(),
    )
    await callback.answer()


@router.callback_query(F.data == "cat_defaults")
async def add_default_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    added = await rq.add_missing_defaults(callback.from_user.id)

    text, markup = await _categories_view(callback.from_user.id)
    await _edit_message(callback.message, text, markup)

    if added:
        await callback.answer(f"Добавлено категорий: {added}")
    else:
        await callback.answer("Все базовые категории уже есть")


# delcat_ok_ должен быть объявлен раньше delcat_, иначе общий фильтр
# перехватит подтверждение удаления.
@router.callback_query(F.data.startswith("delcat_ok_"))
async def confirm_delete_category(callback: CallbackQuery, state: FSMContext):
    category_id = _extract_id(callback.data, "delcat_ok_")
    if category_id is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    deleted_transactions = await rq.delete_category(callback.from_user.id, category_id)
    if deleted_transactions is None:
        await callback.answer("Категория уже удалена", show_alert=True)
        return

    await state.clear()
    text, markup = await _categories_view(callback.from_user.id)
    await _edit_message(callback.message, text, markup)

    if deleted_transactions:
        await callback.answer(f"Удалено операций: {deleted_transactions}")
    else:
        await callback.answer("Категория удалена")


@router.callback_query(F.data.startswith("delcat_"))
async def ask_delete_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    category_id = _extract_id(callback.data, "delcat_")
    if category_id is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    category = await rq.get_category(callback.from_user.id, category_id)
    if category is None:
        await callback.answer("Категория уже удалена", show_alert=True)
        return

    transactions_count = await rq.count_category_transactions(
        callback.from_user.id, category_id
    )

    if transactions_count:
        text = (
            f"Удалить категорию «{category.name}»?\n\n"
            f"Вместе с ней удалятся операции: {transactions_count}. "
            "Это действие нельзя отменить."
        )
    else:
        text = f"Удалить категорию «{category.name}»? В ней нет операций."

    await _edit_message(
        callback.message,
        text,
        kb.confirm_delete_category_keyboard(category.id),
    )
    await callback.answer()


@router.callback_query(F.data == "close")
async def close_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _remove_markup(callback.message)
    await callback.answer()
    await callback.message.answer("Выберите действие в меню.", reply_markup=kb.main)


# --- Статистика -------------------------------------------------------------


@router.callback_query(F.data.startswith("period_"))
async def show_stats(callback: CallbackQuery, state: FSMContext):
    period = callback.data.removeprefix("period_")

    if period not in PERIOD_NAMES:
        await callback.answer("Неизвестный период", show_alert=True)
        return

    await state.clear()
    await _remove_markup(callback.message)

    tg_id = callback.from_user.id
    income, expense = await rq.get_stats(tg_id, period)
    total = income - expense
    category_stats = await rq.get_category_stats(tg_id, period)

    lines = [
        f"📊 Статистика за {PERIOD_NAMES[period]}",
        "",
        f"💰 Доходы: {format_money(income)} ₽",
        f"💸 Расходы: {format_money(expense)} ₽",
        f"📈 Итог: {format_money(total, signed=True)} ₽",
    ]

    if period != "all":
        balance_income, balance_expense = await rq.get_stats(tg_id, "all")
        balance = balance_income - balance_expense
        lines += ["", f"💳 Баланс за всё время: {format_money(balance, signed=True)} ₽"]

    if not category_stats:
        lines += ["", "За этот период операций нет."]

    for category_type, title in ((EXPENSE, "Расходы"), (INCOME, "Доходы")):
        rows = [
            (name, amount)
            for name, row_type, amount in category_stats
            if row_type == category_type
        ]
        if not rows:
            continue

        section_total = expense if category_type == EXPENSE else income
        lines += ["", f"{title} по категориям:"]
        for name, amount in rows:
            percent = round(amount / section_total * 100) if section_total else 0
            lines.append(f"• {name} — {percent}% ({format_money(amount)} ₽)")

    await callback.answer()
    await callback.message.answer("\n".join(lines))


# --- История операций -------------------------------------------------------


@router.callback_query(F.data.startswith("hist_"))
async def history_page(callback: CallbackQuery, state: FSMContext):
    offset = _extract_id(callback.data, "hist_") or 0
    await state.clear()

    text, markup = await _history_view(callback.from_user.id, offset)
    await _edit_message(callback.message, text, markup)
    await callback.answer()


# deltx_ok_ должен быть объявлен раньше deltx_.
@router.callback_query(F.data.startswith("deltx_ok_"))
async def confirm_delete_transaction(callback: CallbackQuery, state: FSMContext):
    payload = _parse_tx_callback(callback.data, "deltx_ok_")
    if payload is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    transaction_id, offset = payload
    deleted = await rq.delete_transaction(callback.from_user.id, transaction_id)
    if not deleted:
        await callback.answer("Операция уже удалена", show_alert=True)
        return

    await state.clear()
    text, markup = await _history_view(callback.from_user.id, offset)
    await _edit_message(callback.message, text, markup)
    await callback.answer("Операция удалена")


@router.callback_query(F.data.startswith("deltx_"))
async def ask_delete_transaction(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    payload = _parse_tx_callback(callback.data, "deltx_")
    if payload is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    transaction_id, offset = payload
    row = await rq.get_transaction(callback.from_user.id, transaction_id)
    if row is None:
        await callback.answer("Операция уже удалена", show_alert=True)
        return

    transaction, category = row
    sign = "−" if transaction.type == EXPENSE else "+"
    text = (
        "Удалить операцию?\n\n"
        f"{transaction.date:%d.%m.%Y} · {category.name} · "
        f"{sign}{format_money(transaction.amount)} ₽"
    )

    await _edit_message(
        callback.message,
        text,
        kb.confirm_delete_transaction_keyboard(transaction.id, offset),
    )
    await callback.answer()


# --- Отмена и устаревшие нажатия -------------------------------------------


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _remove_markup(callback.message)
    await callback.answer("Отменено")
    await callback.message.answer("Действие отменено.", reply_markup=kb.main)


@router.callback_query()
async def stale_callback(callback: CallbackQuery):
    await callback.answer(
        "Кнопка устарела. Откройте меню и попробуйте снова.",
        show_alert=True,
    )


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "Не понял сообщение. Воспользуйтесь меню ниже или отправьте /start.",
        reply_markup=kb.main,
    )
