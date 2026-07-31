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