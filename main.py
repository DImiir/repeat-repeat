from aiogram import Bot, Dispatcher
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram import F

from database.models import UserORM, DictionaryORM
from keyboards import keyboard_menu, keyboard_dict
from database import db_session

BOT_TOKEN = 'BOT_TOKEN'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class AddWordFSM(StatesGroup):
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
Я бот-помощник для изучения тобой иностранных языков.
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
async def open_dictionary_command(message: Message):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    text = [i.word for i in data.dictionary]
    translated = [i.translated_word for i in data.dictionary]
    final_text = '\n'.join([f'{text[i]} - {translated[i]}' for i in range(len(text))])
    await message.answer(f'''
Вот Ваш словарь.
{final_text}
''', reply_markup=keyboard_dict)


@dp.callback_query(F.data == 'add_word')
async def add_word_to_the_dictionary_command(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('''
Что за слово ?
''')
    await state.set_state(AddWordFSM.add)


@dp.message(StateFilter(AddWordFSM.add), F.text)
async def word_is_added_to_the_dictionary(message: Message, state: FSMContext):
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    language = 'английский'
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
Ваше слово занесено в словарь для английского языка    
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
