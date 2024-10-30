from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# строитель клавиатур
def keyboard_maker(data: list[str], width: int, one_time: bool = False):
    kb = ReplyKeyboardBuilder()
    buttons = [KeyboardButton(text=text) for text in data]

    kb.row(*buttons, width=width)

    keyboard: ReplyKeyboardMarkup = kb.as_markup(
        one_time_keyboard=one_time,
        resize_keyboard=True
    )

    return keyboard


def inline_keyboard_maker(number: int, amount: int):
    kb = InlineKeyboardBuilder()
    buttons = [InlineKeyboardButton(text='<-', callback_data='next'),
               InlineKeyboardButton(text=f'{number}/{amount}', callback_data='page'),
               InlineKeyboardButton(text='->', callback_data='back'),
               InlineKeyboardButton(text='Добавить слово', callback_data='add_word')]
    kb.row(*buttons, width=3)

    return kb.as_markup()


keyboard_menu = keyboard_maker(['Помощь ❓', 'Открыть словарь 📚', 'Начать тестирование 🎓'], 3)

keyboard_dict = inline_keyboard_maker(1, 1)

