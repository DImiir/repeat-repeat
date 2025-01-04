import os
import re
from random import shuffle
from math import ceil
from pydub import AudioSegment
import numpy as np
from scipy.spatial.distance import cosine
from scipy.signal import correlate

from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.filters import BaseFilter
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State, default_state
from aiogram.types import Message, CallbackQuery
from gtts import gTTS

import languages
from database import db_session
from database.models import UserORM, DictionaryORM, ResultsORM
from keyboards import (keyboard_menu, inline_language_keyboard_maker, inline_dictionary_keyboard_maker,
                       new_dictionary, inline_words_keyboard_maker, inline_tests_keyboard_maker,
                       inline_word_test_answer_keyboard_maker)

BOT_TOKEN = 'BOT_TOKEN'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

TEXT_FOR_COMPARISON = "Привеет"


class FSMinput(StatesGroup):
    choose_dict = State()
    add_word = State()
    choose_lang = State()
    real_add_word = State()
    result_lang = State()
    start_test = State()
    chose_lang = State()
    word_test = State()

    state_test = State()


special_symbols = '''.,:;!?-–"«»'‘’“”()[]{}...+-=*/<>≤≥≠≈∞√$€₽£¥&&||&|^~<<>>*@#\|_/^%'''


class SpecialCharactersFilter(BaseFilter):
    def __init__(self, special_characters: str):
        self.special_characters = set(special_characters)

    async def __call__(self, message: Message) -> bool:
        return not any(char in self.special_characters for char in message.text)


def load_audio(file_path):
    """Загружает аудиофайл и возвращает его в виде массива."""
    audio = AudioSegment.from_file(file_path).set_frame_rate(44100).set_channels(1)
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    return samples


def normalize_audio(samples):
    """Нормализует аудиоданные."""
    return samples / np.max(np.abs(samples))


def compare_audio(file1, file2):
    """Менее строгое сравнение двух аудиофайлов с использованием корреляции."""
    samples1 = normalize_audio(load_audio(file1))
    samples2 = normalize_audio(load_audio(file2))

    # Применяем корреляцию для более гибкого сравнения
    correlation = correlate(samples1, samples2, mode='valid')

    # Нормализуем корреляцию
    correlation_score = np.max(correlation) / (np.linalg.norm(samples1) * np.linalg.norm(samples2))

    return correlation_score


def contains_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Эмодзи лиц
        "\U0001F300-\U0001F5FF"  # Символы и пиктограммы
        "\U0001F680-\U0001F6FF"  # Транспорт и символы
        "\U0001F1E0-\U0001F1FF"  # Флаги
        "\U00002700-\U000027BF"  # Символы
        "\U0001F900-\U0001F9FF"  # Дополнительные эмодзи
        "\U00002600-\U000026FF"  # Дополнительные символы
        "\U00002B50-\U00002B55"  # Звезды и другие
        "]",
        re.UNICODE,
    )
    return bool(emoji_pattern.search(text))


class EmojiFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return not contains_emoji(message.text)


class DigitFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return not any([i.isdigit() for i in message.text])


def calculate_grade(points):
    if points < 4:
        return 2
    elif points < 6:
        return 3
    elif points < 8:
        return 4
    return 5


@dp.message(Command(commands=["start"]), StateFilter(default_state))
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
Моя задача - помочь тебе в этом деле.
Если что-то непонятно -> /help
''', reply_markup=keyboard_menu)


@dp.message(Command(commands=["help"]), StateFilter(default_state))
@dp.message(F.text.in_(['Помощь ❓', 'помощь', 'Помощь']), StateFilter(default_state))
async def user_help_command(message: Message):
    await message.answer('''
/start - запуск/перезапуск бота.
/dict - открыть словарь 
/test - начать проверку 
/cancel - отмена действия
''')


@dp.message(Command(commands='cancel'), StateFilter(default_state))
async def process_cancel_command(message: Message):
    await message.answer(text='''
Это не тот случай, чтобы применить эту функцию ://
''')


@dp.message(Command(commands='cancel'), ~StateFilter(default_state))
async def process_cancel_command_state(message: Message, state: FSMContext):
    await message.answer(text='''
Отмена
''', reply_markup=keyboard_menu)
    await state.clear()


@dp.message(Command(commands=["dict"]), StateFilter(default_state))
@dp.message(F.text.in_(['Открыть словарь 📚', 'Открыть словарь', 'открыть словарь']), StateFilter(default_state))
async def choose_dictionary_command(message: Message, state: FSMContext):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    langs = sorted(list({i.language for i in data.dictionary}))
    if langs:
        m = len(langs)
        amount = ceil(m / 10)
        n = m if m < 10 else 10
        await message.answer(f'''
Вот все Ваши словари.
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount, True))
        await state.set_state(FSMinput.choose_dict)
    else:
        await message.answer(f'''
У Вас нет словарей.
''', reply_markup=new_dictionary)
        await state.set_state(FSMinput.add_word)


@dp.callback_query(F.data.startswith('next_page_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('next_page_dict'), StateFilter(FSMinput.choose_dict))
async def previous_page_dict_command(callback: CallbackQuery):
    if F.data.startswith('next_page_test'):
        page = int(callback.data.lstrip('next_page_test')[-1])
        dict_or_test = False
        text = 'Выберите язык:'
    else:
        page = int(callback.data.lstrip('next_page_dict')[-1])
        dict_or_test = True
        text = 'Вот все Ваши словари.'

    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    langs = sorted(list({i.language for i in data.dictionary}))
    m = len(langs)
    amount = ceil(m / 10)

    if page * 10 < m:
        final_langs = langs[page * 10:]
    else:
        final_langs = langs[page * 10: (page + 1) * 10]

    await callback.message.edit_text(f'''
{text}
''', reply_markup=inline_dictionary_keyboard_maker(final_langs, page + 1, amount, dict_or_test))


@dp.callback_query(F.data.startswith('previous_page_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('previous_page_dict'), StateFilter(FSMinput.choose_dict))
async def previous_page_dict_command(callback: CallbackQuery):
    if F.data.startswith('previous_page_test'):
        page = int(callback.data.lstrip('previous_page_test')[-1])
        dict_or_test = False
        text = 'Выберите язык:'
    else:
        page = int(callback.data.lstrip('previous_page_dict')[-1])
        dict_or_test = True
        text = 'Вот все Ваши словари.'

    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    langs = sorted(list({i.language for i in data.dictionary}))
    final_langs = langs[(page - 2) * 10: (page - 1) * 10]
    amount = ceil(len(langs) / 10)

    await callback.message.edit_text(f'''
{text}
''', reply_markup=inline_dictionary_keyboard_maker(final_langs, page - 1, amount, dict_or_test))


@dp.callback_query(F.data.startswith('dict_'), StateFilter(FSMinput.choose_dict))
async def open_dictionary_command(callback: CallbackQuery, state: FSMContext):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    lang = callback.data.lstrip('dict_')
    text = [(i.word, i.translated_word) for i in data.dictionary if i.language == lang]
    m = len(text)
    amount = ceil(m / 10)
    n = m if m < 10 else 10
    final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[:n]])
    await callback.message.edit_text(f'''
{final_text}
''', reply_markup=inline_words_keyboard_maker(lang, 1, amount))
    await state.set_state(FSMinput.add_word)


@dp.callback_query(F.data.startswith('next_page_words_'), StateFilter(FSMinput.add_word))
async def previous_page_words_command(callback: CallbackQuery):
    page = int(callback.data.split('_')[-1])
    lang = callback.data.split('_')[-2]

    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    text = [(i.word, i.translated_word) for i in data.dictionary if i.language == lang]
    m = len(text)
    amount = ceil(m / 10)

    if page * 10 < m:
        final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[page * 10:]])
    else:
        final_text = '\n'.join([f'{i[0]} - {i[1]}' for i in text[page * 10: (page + 1) * 10]])

    await callback.message.edit_text(f'''
{final_text}
''', reply_markup=inline_words_keyboard_maker(lang, page + 1, amount))


@dp.callback_query(F.data.startswith('previous_page_words_'), StateFilter(FSMinput.add_word))
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


@dp.callback_query(F.data == 'choose_language', StateFilter(FSMinput.add_word))
@dp.callback_query(F.data == 'choose_language', StateFilter(FSMinput.choose_dict))
async def choose_language_add_word_command(callback: CallbackQuery, state: FSMContext):
    amount = ceil(len(languages.items) / 10)

    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(languages.items[:10], 1, amount))
    await state.set_state(FSMinput.choose_lang)


@dp.callback_query(F.data.startswith('next_page_lang'), StateFilter(FSMinput.choose_lang))
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


@dp.callback_query(F.data.startswith('previous_page_lang'), StateFilter(FSMinput.choose_lang))
async def previous_page_lang_command(callback: CallbackQuery):
    amount = ceil(len(languages.items) / 10)

    page = int(callback.data.lstrip('previous_page_lang'))

    items = languages.items[(page - 2) * 10: (page - 1) * 10]

    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(items, page - 1, amount))


@dp.callback_query(F.data.startswith('language_'), StateFilter(FSMinput.choose_lang))
async def choose_language_dictionary_command(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language=callback.data.split('language_')[1])
    await callback.message.edit_text('''
Что за слово ?
''')
    await state.set_state(FSMinput.real_add_word)


@dp.message(F.text, DigitFilter(), SpecialCharactersFilter(special_symbols), EmojiFilter(), StateFilter(FSMinput.real_add_word))
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
Ваше слово занесено в словарь.
''', reply_markup=keyboard_menu)
    await state.clear()


@dp.message(F.text, StateFilter(FSMinput.real_add_word))
async def message_contains_special_symbol(message: Message):
    await message.answer('''
Слово не должно содержать цифры, специальные символы или эмодзи.
''')


@dp.message(StateFilter(FSMinput.real_add_word))
async def it_is_not_word(message: Message):
    await message.answer('''
Это нельзя добавить в словарь.
''')


@dp.message(Command(commands=["results"]), StateFilter(default_state))
@dp.message(F.text.in_(['Результаты']), StateFilter(default_state))
async def check_results(message: Message, state: FSMContext):
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    langs = sorted(set([(i.language, languages.lexicon[i.language]) for i in user.statistics]))
    await state.update_data(languages=langs)
    m = len(langs)
    amount = ceil(m / 10)
    await message.answer('''
Выберите язык, по которому хотите посмотреть результаты:
''', reply_markup=inline_language_keyboard_maker(langs, 1, amount))
    await state.set_state(FSMinput.result_lang)


@dp.callback_query(F.data.startswith('next_page_lang'), StateFilter(FSMinput.result_lang))
async def next_page_lang_result_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    amount = ceil(len(data['languages']) / 10)

    page = int(callback.data.lstrip('next_page_lang'))

    if page * 10 >= len(data['languages']):
        items = data['languages'][page * 10:]
    else:
        items = data['languages'][page * 10: (page + 1) * 10]

    await callback.message.edit_text('''
Выберите язык, по которому хотите посмотреть результаты:
''', reply_markup=inline_language_keyboard_maker(items, page + 1, amount))


@dp.callback_query(F.data.startswith('previous_page_lang'), StateFilter(FSMinput.result_lang))
async def previous_page_lang_result_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    amount = ceil(len(data['languages']) / 10)

    page = int(callback.data.lstrip('previous_page_lang'))

    items = data['languages'][(page - 2) * 10: (page - 1) * 10]

    await callback.message.edit_text('''
Выберите язык, по которому хотите посмотреть результаты:
''', reply_markup=inline_language_keyboard_maker(items, page - 1, amount))


@dp.callback_query(F.data.startswith('language_'), StateFilter(FSMinput.result_lang))
async def check_results_of_tests(callback: CallbackQuery, state:FSMContext):
    language = callback.data.lstrip('language_')
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    grades = sorted([(i.type_of_tests, i.result) for i in user.statistics if i.language == language], key=lambda x: x[0])

    text = ''
    for i in grades:
        if i[0] == 1:
            text += f'Словесный - {i[1]}\n'
        if i[0] == 2:
            text += f'Фразовый - {i[1]}\n'
        if i[0] == 3:
            text += f'По картинкам - {i[1]}\n'
        if i[0] == 4:
            text += f'Аудио - {i[1]}\n'

    await callback.message.edit_text(f'''
Вот Ваши оценки по языку {languages.lexicon[language]}:
{text}
''')
    await callback.answer(reply_markup=keyboard_menu)
    await state.clear()


@dp.message(Command(commands=["test"]), StateFilter(default_state))
@dp.message(F.text.in_(['Пройти тест 🎓', 'пройти тест', 'Пройти тест']), StateFilter(default_state))
async def start_test_command(message: Message, state: FSMContext):
    await message.answer('''
Выберите тип тестирования:
''', reply_markup=inline_tests_keyboard_maker())
    await state.set_state(FSMinput.start_test)


@dp.callback_query(F.data == 'word_test', StateFilter(FSMinput.start_test))
async def choose_word_test_type(callback: CallbackQuery, state: FSMContext):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    all_langs = [i.language for i in data.dictionary]
    langs = sorted({i for i in all_langs if all_langs.count(i) >= 10})
    if langs:
        m = len(langs)
        amount = ceil(m / 10)
        n = m if m < 10 else 10
        await callback.message.edit_text(f'''
Выберите язык:
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount, False))
        await state.set_state(FSMinput.choose_dict)
    else:
        await callback.message.edit_text(f'''
У Вас нет словарей, по которым можно составить тест.
''', reply_markup=new_dictionary)
        await state.set_state(FSMinput.add_word)


@dp.callback_query(F.data.startswith('test'), StateFilter(FSMinput.choose_dict))
async def word_test_running(callback: CallbackQuery, state: FSMContext):
    language = callback.data.split('_')[-1]
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    n, rating = 0, 0
    words = [(i.word, i.translated_word) for i in data.dictionary if i.language == language][:10]
    shuffle(words)
    await callback.message.edit_text(f'''
Как переводится это:
{words[n][0]}
''', reply_markup=inline_word_test_answer_keyboard_maker([i[1] for i in words], n))
    await state.set_state(FSMinput.word_test)
    await state.update_data(language=language, words=words, n=n, rating=rating)


@dp.callback_query(F.data.startswith('wordtest'), StateFilter(FSMinput.word_test))
async def word_test_answering(callback: CallbackQuery, state: FSMContext):
    info = await state.get_data()
    info['n'] += 1
    grade = calculate_grade(info['rating'])

    if callback.data.split('_')[-1] == 'true':
        info['rating'] += 1

    await state.update_data(n=info['n'], rating=info['rating'])

    if info['n'] == 10:
        await callback.message.edit_text(f'''
Ты прошёл тест.
Твой результат: {info['rating']}/10
Это {grade}
''')
        await callback.answer(reply_markup=keyboard_menu)

        session = db_session.create_session()
        user = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
        stat = [i for i in user.statistics if i.language == info['language']]
        if stat:
            stat[0].number_of_attempts += 1
            stat[0].result = (stat[0].result * (stat[0].number_of_attempts - 1) + grade) / stat[0].number_of_attempts
        else:
            data = ResultsORM(
                user_id=user.id,
                language=info['language'],
                type_of_tests=1,
                result=grade,
                number_of_attempts=1
            )
            user.statistics.append(data)
            session.add(user)
        session.commit()

        await state.clear()
    else:
        await callback.message.edit_text(f'''
Как переводится это:
{info['words'][info['n']][0]}
''', reply_markup=inline_word_test_answer_keyboard_maker([i[1] for i in info['words']], info['n']))


@dp.callback_query(F.data.startswith('audio_test'), StateFilter(FSMinput.start_test))
async def choose_system_test_type(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('''
Введите текст для аудио:
''')
    await state.set_state(FSMinput.state_test)


@dp.message(StateFilter(FSMinput.state_test), F.content_type.in_({'audio', 'voice'}))
async def ststststtst(message: Message):
    user_id = message.from_user.id
    file_id = message.voice.file_id

    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    user_audio_file = f"{user_id}_voice.ogg"
    await bot.download_file(file_path, user_audio_file)

    user_audio_wav = f"{user_id}_voice.wav"
    AudioSegment.from_file(user_audio_file).export(user_audio_wav, format="wav")

    system_audio_file = "system_audio.mp3"
    tts = gTTS(TEXT_FOR_COMPARISON, lang='ru')
    tts.save(system_audio_file)

    system_audio_wav = "system_audio.wav"
    AudioSegment.from_mp3(system_audio_file).export(system_audio_wav, format="wav")

    try:
        correlation_score = compare_audio(system_audio_wav, user_audio_wav)
        await message.reply(f"Схожесть с синтезированным голосом: {correlation_score:.2f}")
    except Exception as e:
        await message.reply(f"Произошла ошибка при сравнении: {e}")
    finally:
        os.remove(user_audio_file)
        os.remove(user_audio_wav)
        os.remove(system_audio_file)
        os.remove(system_audio_wav)


if __name__ == '__main__':
    db_session.global_init('database/langdict.sqlite')
    dp.run_polling(bot)
