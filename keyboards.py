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


def inline_pagination_maker(number: int, amount: int):
    kb = InlineKeyboardBuilder()
    buttons = [InlineKeyboardButton(text='<-', callback_data='previous'),
               InlineKeyboardButton(text=f'{number}/{amount}', callback_data='page'),
               InlineKeyboardButton(text='->', callback_data='next'),
               InlineKeyboardButton(text='Добавить слово', callback_data='choose_language')]
    kb.row(*buttons, width=3)

    return kb.as_markup()


def inline_language_keyboard_maker(items: list[tuple], page: int, amount: int):
    kb = InlineKeyboardBuilder()

    for i in items:
        kb.row(InlineKeyboardButton(text=f'{i[0]}', callback_data=f'language_{i[1]}'), width=1)

    if page == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_lang{page}')], width=2)
    elif page == amount:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_lang{page}'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')], width=2)
    else:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_lang{page}'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_lang{page}')], width=3)

    return kb.as_markup()


keyboard_menu = keyboard_maker(['Помощь ❓', 'Открыть словарь 📚', 'Начать тестирование 🎓'], 3)

keyboard_dict = inline_pagination_maker(1, 1)


