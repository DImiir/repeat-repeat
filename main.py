from aiogram import Bot, Dispatcher
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram import F

from database.models import UserORM, DictionaryORM
from keyboards import (keyboard_menu, inline_language_keyboard_maker, inline_dictionary_keyboard_maker,
                       new_dictionary, inline_words_keyboard_maker)
from database import db_session

import languages

from math import ceil

BOT_TOKEN = 'BOT_TOKEN'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class FSMMachine(StatesGroup):
    dict = State()
    choose = State()
    add = State()


@dp.message(Command(commands=["start"]))
async def process_start_command(message: Message):
    info = message.model_dump()['from_user']
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == info['id']).one_or_none()
    if user is None:
        user = UserORM(
            tg_id=info['id'],
            username=info['username']
        )
        session.add(user)
        session.commit()
    await message.answer('''
Привет !!!
Я бот для изучения иностранных языков.
Моя задача - помочь запомнить слова и их перевод.
Если что-то непонятно -> /help
''', reply_markup=keyboard_menu)


@dp.message(Command(commands=["help"]))
@dp.message(F.text.in_(['Помощь ❓', 'помощь', 'Помощь']))
async def user_help_command(message: Message):
    await message.answer('''
/start - запуск/перезапуск бота.
/dict - открыть словарь 
/test - начать проверку 
/cancel - отмена действия
''')


@dp.message(Command(commands=["dict"]))
@dp.message(F.text.in_(['Открыть словарь 📚', 'Открыть словарь', 'открыть словарь']))
async def choose_dictionary_command(message: Message):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    langs = sorted(list({i.language for i in data.dictionary}))
    if langs:
        m = len(langs)
        amount = ceil(m / 10)
        n = m if m < 10 else 10
        await message.answer(f'''
Вот все Ваши словари.
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount))
    else:
        await message.answer(f'''
У Вас нет словарей.
''', reply_markup=new_dictionary)


@dp.callback_query(F.data.startswith('dictionary_'))
async def open_dictionary_command(callback: CallbackQuery):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    lang = callback.data.lstrip('dictionary_')
    text = [(i.word, i.translated_word) for i in data.dictionary if i.language == lang]
    m = len(text)
    amount = ceil(m / 10)
    n = m if m < 10 else 10
    final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[:n]])
    await callback.message.edit_text(f'''
{final_text}
''', reply_markup=inline_words_keyboard_maker(lang, 1, amount))


@dp.callback_query(F.data.startswith('next_page_words_'))
async def previous_page_words_command(callback: CallbackQuery):
    page = int(callback.data.split('_')[-1])
    lang = callback.data.split('_')[-2]

    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    text = [(i.word, i.translated_word) for i in data.dictionary if i.language == lang]
    amount = ceil(len(text) / 10)

    if page * 10 < len(text):
        final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[page * 10:]])
    else:
        final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[page * 10: (page + 1) * 10]])

    await callback.message.edit_text(f'''
{final_text}
''', reply_markup=inline_words_keyboard_maker(lang, page + 1, amount))


@dp.callback_query(F.data.startswith('previous_page_words_'))
async def previous_page_words_command(callback: CallbackQuery):
    page = int(callback.data.split('_')[-1])
    lang = callback.data.split('_')[-2]

    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    text = [(i.word, i.translated_word) for i in data.dictionary if i.language == lang]
    final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[(page - 2) * 10: (page - 1) * 10]])
    amount = ceil(len(text) / 10)

    await callback.message.edit_text(f'''
{final_text}
''', reply_markup=inline_words_keyboard_maker(lang, page - 1, amount))


@dp.callback_query(F.data == 'choose_language')
async def choose_language_add_word_command(callback: CallbackQuery, state: FSMContext):
    amount = ceil(len(languages.items) / 10)

    await state.set_state(FSMMachine.choose)
    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(languages.items[:10], 1, amount))


@dp.callback_query(StateFilter(FSMMachine.choose), F.data.startswith('next_page_lang'))
async def next_page_lang_command(callback: CallbackQuery):
    amount = ceil(len(languages.items) / 10)

    page = int(callback.data.lstrip('next_page_lang'))

    if page * 10 >= len(languages.items):
        items = languages.items[page * 10:]
    else:
        items = languages.items[page * 10: (page + 1) * 10]

    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(items, page + 1, amount))


@dp.callback_query(StateFilter(FSMMachine.choose), F.data.startswith('previous_page_lang'))
async def next_page_lang_command(callback: CallbackQuery):
    amount = ceil(len(languages.items) / 10)

    page = int(callback.data.lstrip('previous_page_lang'))

    items = languages.items[(page - 2) * 10: (page - 1) * 10]

    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(items, page - 1, amount))


@dp.callback_query(StateFilter(FSMMachine.choose), F.data.startswith('language_'))
async def choose_language_dictionary_command(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language=callback.data.split('language_')[1])
    await callback.message.edit_text('''
Что за слово ?
''')
    await state.set_state(FSMMachine.add)


@dp.message(StateFilter(FSMMachine.add), F.text)
async def word_is_added_to_the_dictionary(message: Message, state: FSMContext):
    lang = await state.get_data()
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    language = lang['language']
    word = message.text
    translated_word = word
    data = DictionaryORM(
        user_id=user.id,
        language=language,
        word=word,
        translated_word=translated_word
    )
    user.dictionary.append(data)
    session.add(user)
    session.commit()
    await message.answer('''
Ваше слово занесено в словарь    
''', reply_markup=keyboard_menu)
    await state.clear()


@dp.message(Command(commands=["test"]))
@dp.message(F.text.in_(['Начать проверку 🎓', 'начать проверку', 'Начать проверку']))
async def start_test_command(message: Message):
    await message.answer('''
По какому языку Вы хотите начать тестирование ?    
''')


if __name__ == '__main__':
    db_session.global_init('database/langdict.sqlite')
    dp.run_polling(bot)
