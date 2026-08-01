from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import app.keyboards as kb
from app.states import AddTransaction

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет, я твой помощник по финансам!", reply_markup=kb.main)


@router.message(F.text == "Добавить расход")
async def add_transaction(message: Message, state: FSMContext):
    await state.set_state(AddTransaction.choosing_category)
    await message.answer("Выберите категорию", reply_markup=kb.get_categories_keyboard())


@router.callback_query(F.data.startswith("categ_"), AddTransaction.choosing_category)
async def category_selection(callback: CallbackQuery, state: FSMContext):
    category_name = callback.data.split("_")[1]
    await state.update_data(category=category_name)
    await state.set_state(AddTransaction.enter_amount)
    await callback.answer()
    await callback.message.answer("Вы выбрали категорию. Теперь введите сумму")



