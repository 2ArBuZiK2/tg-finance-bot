from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardButton, InlineKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import get_categories_by_user_and_type


main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Добавить расход"),
                                      KeyboardButton(text="Добавить доход")],
                           [KeyboardButton(text="Управление категориями")]],
                           resize_keyboard=True)

async def get_expense_keyboard(tg_id: int):
    keyboard = InlineKeyboardBuilder()

    categories = await get_categories_by_user_and_type(tg_id, 'expense')
    for cat in categories:
        keyboard.button(text=cat.name, callback_data=f'categ_{cat.id}')

    return keyboard.adjust(2).as_markup()



async def get_income_keyboard(tg_id: int):
    keyboard = InlineKeyboardBuilder()

    categories = await get_categories_by_user_and_type(tg_id, 'income')
    for cat in categories:
        keyboard.button(text=cat.name, callback_data=f'categ_{cat.id}')

    return keyboard.adjust(2).as_markup()

def get_type_category():
    keyboard = InlineKeyboardBuilder()

    categories = [
        ("Расход", "type_expense"), ("Доход", "type_income")
    ]
    for text, callback in categories:
        keyboard.button(text=text, callback_data=callback)

    return keyboard.adjust(2).as_markup()



