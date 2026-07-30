from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardButton, InlineKeyboardMarkup)


main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Добавить расход"),
                                      KeyboardButton(text="Добавить доход")]],
                           resize_keyboard=True)