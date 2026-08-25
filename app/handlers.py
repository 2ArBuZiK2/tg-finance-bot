from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import app.keyboards as kb
from app.states import AddTransaction, AddCategory
import app.database.requests as rq

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await rq.set_user(message.from_user.id)
    await message.answer("Привет, я твой помощник по финансам!", reply_markup=kb.main)


@router.message(F.text == "Добавить расход")
async def add_expense(message: Message, state: FSMContext):
    await state.set_state(AddTransaction.choosing_category)
    await message.answer("Выберите категорию", reply_markup=await kb.get_expense_keyboard(message.from_user.id))


@router.callback_query(F.data.startswith("categ_"), AddTransaction.choosing_category)
async def category_selection(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AddTransaction.enter_amount)
    await callback.answer()
    await callback.message.answer("Вы выбрали категорию. Теперь введите сумму")


@router.message(AddTransaction.enter_amount)
async def enter_amount(message: Message, state: FSMContext):
    await state.update_data(amount=message.text)


@router.message(F.text == "Добавить доход")
async def add_income(message: Message, state: FSMContext):
    await state.set_state(AddTransaction.choosing_category)
    await message.answer("Выберите категорию", reply_markup=await kb.get_income_keyboard(message.from_user.id))


@router.message(F.text == "Управление категориями")
async def manage_categories(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddCategory.name)
    await message.answer("Введите название новой категории")


@router.message(AddCategory.name)
async def add_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(AddCategory.type)
    await message.answer("Выберите тип категории:", reply_markup=kb.get_type_category())


@router.callback_query(F.data.startswith("type_"), AddCategory.type)
async def type_category(callback: CallbackQuery, state: FSMContext):
    category_type = callback.data.split("_")[1]
    data = await state.get_data()
    name = data.get("category")

    result = await rq.add_category(tg_id=callback.from_user.id, name=name, type=category_type)

    if result:
        await callback.message.answer(f"✅ Категория '{name}' добавлена!")
    else:
        await callback.message.answer(f"⚠️ Категория '{name}' уже существует или произошла ошибка.")

    await state.clear()
    await callback.answer()
