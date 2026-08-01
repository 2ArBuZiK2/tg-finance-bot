from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardButton, InlineKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder


main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Добавить расход"),
                                      KeyboardButton(text="Добавить доход")]],
                           resize_keyboard=True)

def get_expense_keyboard():
    keyboard = InlineKeyboardBuilder()

    categories = [
        ("🍔 Еда", "categ_food"),
        ("🚗 Транспорт", "categ_transport"),
        ("🏠 Жилье", "categ_house"),
        ("🎬 Отдых", "categ_fun")
    ]

    for text, callback in categories:
        keyboard.button(text=text, callback_data=callback)

    return keyboard.adjust(2).as_markup()

def get_income_keyboard():
    keyboard = InlineKeyboardBuilder()

    categories = [
        ("💸 Зарплата", "inc_salary"), ("💼 Фриланс", "inc_freelance"),
        ("🎁 Подарки", "inc_gifts")
    ]
    for text, callback in categories:
        keyboard.button(text=text, callback_data=callback)

    return keyboard.adjust(2).as_markup()



