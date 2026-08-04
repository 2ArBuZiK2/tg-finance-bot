from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext


class AddTransaction(StatesGroup):
    choosing_category = State()
    enter_amount = State()

class AddCategory(StatesGroup):
    name  = State()
    type = State()