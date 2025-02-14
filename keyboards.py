from random import shuffle

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import lexicon


def keyboard_maker(data: list[str], width: int, one_time: bool = False):
    kb = ReplyKeyboardBuilder()
    buttons = [KeyboardButton(text=text) for text in data]

    kb.row(*buttons, width=width)

    keyboard: ReplyKeyboardMarkup = kb.as_markup(
        one_time_keyboard=one_time,
        resize_keyboard=True
    )

    return keyboard


def inline_dictionary_keyboard_maker(items: list[str], page: int, amount: int, prefix: str):
    kb = InlineKeyboardBuilder()

    for item in items:
        kb.row(InlineKeyboardButton(text=lexicon.languages[item], callback_data=f'{prefix}_{item}'))

    if amount == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')])
    elif page == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_{prefix}_{page}')])
    elif page == amount:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_{prefix}_{page}'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')])
    else:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_{prefix}_{page}'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_{prefix}_{page}')])

    if prefix == 'dict':
        kb.row(InlineKeyboardButton(text='Добавить слово', callback_data='choose_language'))

    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))

    return kb.as_markup()


def inline_language_keyboard_maker(items: list, page: int, amount: int, lang_or_test: str):
    kb = InlineKeyboardBuilder()

    prefix = lang_or_test

    for i in items:
        kb.row(InlineKeyboardButton(text=f'{lexicon.languages[i]}', callback_data=f'{prefix}_{i}'), width=1)

    if amount == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')])
    elif page == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_{prefix}_{page}')])
    elif page == amount:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_{prefix}_{page}'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')])
    else:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_{prefix}_{page}'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_{prefix}_{page}')])

    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))

    return kb.as_markup()


def inline_make_dictionary():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text='Добавить слово', callback_data='choose_language'))
    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))
    return kb.as_markup()


def inline_words_keyboard_maker(words: list[tuple], page: int, amount: int, lang=''):
    kb = InlineKeyboardBuilder()

    final_words = words[(page - 1) * 10:page * 10]

    for i in final_words:
        kb.row(InlineKeyboardButton(text=f'{i[0]} - {i[1]}', callback_data=f'word_{i[2]}'))

    if amount == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')])
    elif page == 1:
        kb.row(*[InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_words')])
    elif page == amount:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_words'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page')])
    else:
        kb.row(*[InlineKeyboardButton(text='<-', callback_data=f'previous_page_words'),
                 InlineKeyboardButton(text=f'{page}/{amount}', callback_data='page'),
                 InlineKeyboardButton(text='->', callback_data=f'next_page_words')])
    kb.row(InlineKeyboardButton(text='Добавить слово', callback_data=f'choose_language_{lang}'))
    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))

    return kb.as_markup()


def inline_word_keyboard_maker(word_id: int):
    kb = InlineKeyboardBuilder()

    kb.row(InlineKeyboardButton(text='Удалить', callback_data=f'delete_word_{word_id}'))
    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))

    return kb.as_markup()


def inline_tests_keyboard_maker():
    kb = InlineKeyboardBuilder()
    kb.row(*[InlineKeyboardButton(text='Индивидуальный', callback_data=f'word_test'),
             InlineKeyboardButton(text='Системный', callback_data=f'phrase_test'),
             InlineKeyboardButton(text='По картинкам', callback_data=f'picture_test'),
             InlineKeyboardButton(text='Аудио тест', callback_data=f'audio_test')], width=1)

    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))

    return kb.as_markup()


def inline_word_test_answer_keyboard_maker(variants: list[str], n: int, type: str):
    kb = InlineKeyboardBuilder()
    true_variant = variants[n]
    variants.remove(true_variant)
    shuffle(variants)
    possible_answers = variants[:4]
    possible_answers.append(true_variant)
    shuffle(possible_answers)
    for variant in possible_answers:
        if variant == true_variant:
            kb.row(InlineKeyboardButton(text=f'{variant}', callback_data=f'{type}_answer_true'))
        else:
            kb.row(InlineKeyboardButton(text=f'{variant}', callback_data=f'{type}_answer_false'))
    return kb.as_markup()


def inline_phrase_audio_picture_test_group_keyboard_maker(lang: str, groups: set, prefix: str):
    kb = InlineKeyboardBuilder()
    lexgroups = dict()
    if prefix == 'phrase':
        lexgroups = lexicon.phrase_groups
    elif prefix == 'picture':
        lexgroups = lexicon.pictures_groups
    elif prefix == 'audio':
        lexgroups = lexicon.audio_groups

    if prefix == 'audio':
        for i in sorted(groups):
            kb.row(InlineKeyboardButton(text=lexgroups[i], callback_data=f'{prefix}_test_{i}'))
    else:
        for i in sorted(groups):
            kb.row(InlineKeyboardButton(text=lexgroups[i], callback_data=f'{prefix}_test_{i}_{lang}'))
    kb.row(InlineKeyboardButton(text='Отмена', callback_data='cancel_action'))
    return kb.as_markup()


keyboard_menu = keyboard_maker(['Помощь ❓', 'Открыть словарь 📚', 'Пройти тест 🎓', 'Результаты '], 2)

new_dictionary = inline_make_dictionary()
