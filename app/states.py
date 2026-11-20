from aiogram.fsm.state import State, StatesGroup


class AddTransaction(StatesGroup):
    choosing_category = State()
    enter_amount = State()


class AddCategory(StatesGroup):
    name = State()
    type = State()
