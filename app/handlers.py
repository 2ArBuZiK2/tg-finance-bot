from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import app.database.requests as rq
import app.keyboards as kb
from app.states import AddCategory, AddTransaction
from app.utils import MAX_AMOUNT, MAX_CATEGORY_NAME, format_money, parse_amount

router = Router()

EXPENSE = "expense"
INCOME = "income"

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
    await state.set_state(AddCategory.name)
    await message.answer(
        f"Введите название новой категории (до {MAX_CATEGORY_NAME} символов)"
        " или отправьте /cancel:",
        reply_markup=kb.cancel_inline(),
    )


@router.message(F.text == "Статистика")
async def stats(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите период:", reply_markup=kb.get_period_keyboard())


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

    await state.clear()
    await _remove_markup(callback.message)

    if result:
        text = f"✅ Категория «{name}» добавлена."
    else:
        text = f"⚠️ Категория «{name}» уже существует."

    await callback.answer()
    await callback.message.answer(text, reply_markup=kb.main)


# --- Статистика -------------------------------------------------------------


@router.callback_query(F.data.startswith("period_"))
async def show_stats(callback: CallbackQuery, state: FSMContext):
    period = callback.data.removeprefix("period_")

    if period not in PERIOD_NAMES:
        await callback.answer("Неизвестный период", show_alert=True)
        return

    await state.clear()
    await _remove_markup(callback.message)

    income, expense = await rq.get_stats(callback.from_user.id, period)
    total = income - expense

    text = (
        f"📊 Статистика за {PERIOD_NAMES[period]}\n\n"
        f"💰 Доходы: {format_money(income)} ₽\n"
        f"💸 Расходы: {format_money(expense)} ₽\n"
        f"📈 Итог: {format_money(total, signed=True)} ₽"
    )

    await callback.answer()
    await callback.message.answer(text)


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
