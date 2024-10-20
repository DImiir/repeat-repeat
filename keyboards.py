from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


buttons = [KeyboardButton(text='Помощь ❓'),
           KeyboardButton(text='Открыть словарь 📚'),
           KeyboardButton(text='Начать тестирование 🎓')]

keyboard_builder = ReplyKeyboardBuilder()
keyboard_builder.row(*buttons, width=3)
keyboard_menu: ReplyKeyboardMarkup = keyboard_builder.as_markup(
    resize_keyboard=True
)

