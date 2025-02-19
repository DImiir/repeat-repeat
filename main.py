import os
import re
from pathlib import Path
from random import shuffle
from math import ceil
from shutil import rmtree
import time

import aiofiles
import requests
from aiogram.client.session import aiohttp

from pydub import AudioSegment
import numpy as np
from scipy.signal import correlate
from Levenshtein import distance as levenshtein_distance
import speech_recognition as sr

from aiogram import Bot, Dispatcher
from aiogram import F
from aiogram.filters import BaseFilter
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State, default_state
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from gtts import gTTS

import lexicon
from database import db_session
from database.models import UserORM, DictionaryORM, ResultsORM, SystemInfoORM, PictureInfoORM
from keyboards import (keyboard_menu, inline_language_keyboard_maker, inline_dictionary_keyboard_maker,
                       new_dictionary, inline_words_keyboard_maker, inline_tests_keyboard_maker,
                       inline_word_test_answer_keyboard_maker, inline_word_keyboard_maker,
                       inline_phrase_audio_picture_test_group_keyboard_maker)

BOT_TOKEN = ''
API_key = ''
bot = Bot(token=BOT_TOKEN, proxy='http://proxyprovider.com:2116')
dp = Dispatcher()


def translate(text, target_language):
    body = {
        "targetLanguageCode": target_language,
        "texts": text,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {API_key}"
    }

    response = requests.post('https://translate.api.cloud.yandex.net/translate/v2/translate',
                             json=body,
                             headers=headers)

    return response.json()['translations'][0]['text']


def text_to_audio(text: str, lang: str, file_name: str = "audio.mp3") -> str:
    tts = gTTS(text, lang=lang)
    tts.save(file_name)
    return file_name


class FSMinput(StatesGroup):
    choose_dict = State()
    word = State()
    choose_lang = State()
    real_add_word = State()
    result_lang = State()
    start_test = State()
    test = State()
    audio_test = State()


special_symbols = '''.,:;!?-–"«»'‘’“”()[]{}...+-=*/<>≤≥≠≈∞√$€₽£¥&&||&|^~<<>>*@#\|_/^%'''


class SpecialCharactersFilter(BaseFilter):
    def __init__(self, special_characters: str):
        self.special_characters = set(special_characters)

    async def __call__(self, message: Message) -> bool:
        return not any(char in self.special_characters for char in message.text)


def load_audio(file_path):
    audio = AudioSegment.from_file(file_path).set_frame_rate(44100).set_channels(1)
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    return samples


def normalize_audio(samples):
    return samples / np.max(np.abs(samples))


def compare_audio(file1, file2):
    samples1 = normalize_audio(load_audio(file1))
    samples2 = normalize_audio(load_audio(file2))

    correlation = correlate(samples1, samples2, mode='valid')

    correlation_score = np.max(correlation) / (np.linalg.norm(samples1) * np.linalg.norm(samples2))

    return correlation_score


TEMP_PATH = "temp_audio"
os.makedirs(TEMP_PATH, exist_ok=True)

THRESHOLD = 0.1


def normalize_text(text):
    return re.sub(r'[^\w\s]', '', text).strip().lower()


def preprocess_audio(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    if len(audio) > 5000:
        audio = audio[:5000]
    audio.export(output_path, format="wav")


def is_similar(text1, text2, threshold=THRESHOLD):
    text1, text2 = normalize_text(text1), normalize_text(text2)
    max_len = max(len(text1), len(text2))
    if max_len == 0:
        return False
    similarity = levenshtein_distance(text1, text2) / max_len
    return similarity <= threshold


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
    session.close()


@dp.message(Command(commands=["help"]), StateFilter(default_state))
@dp.message(F.text.in_(['Помощь ❓', 'помощь', 'Помощь']), StateFilter(default_state))
async def user_help_command(message: Message):
    await message.answer('''
/start - запуск/перезапуск бота.
/dict - открыть словарь 
/test - начать проверку 
/results - посмотреть результаты
/cancel & Отмена - отмена действия
''')


@dp.message(Command(commands='cancel'), StateFilter(default_state))
async def process_cancel_command(message: Message):
    await message.answer(text='''
Это не тот случай, чтобы применить эту команду
''')


@dp.message(Command(commands='cancel'), ~StateFilter(default_state))
async def process_cancel_command_state(message: Message, state: FSMContext):
    await message.answer(text='''
Отмена
''', reply_markup=keyboard_menu)
    await state.clear()


@dp.callback_query(F.data == 'cancel_action', ~StateFilter(default_state))
async def process_cancel_command_state(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer('''
Отмена
''')
    await callback.answer(reply_markup=keyboard_menu)
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
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount, 'dict'))
        await state.set_state(FSMinput.choose_dict)
    else:
        await message.answer(f'''
У Вас нет словарей.
''', reply_markup=new_dictionary)
        await state.set_state(FSMinput.word)
    session.close()


@dp.callback_query(F.data.startswith('next_page_word_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('next_page_dict'), StateFilter(FSMinput.choose_dict))
async def previous_page_dict_command(callback: CallbackQuery):
    lst = callback.data.split('_')
    page = int(lst[-1])
    prefix = lst[-2]
    if prefix == 'test':
        dict_or_test = lst[-3]
        text = 'Выберите язык:'
    else:
        dict_or_test = 'dict'
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
    session.close()


@dp.callback_query(F.data.startswith('previous_page_word_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('previous_page_dict'), StateFilter(FSMinput.choose_dict))
async def previous_page_dict_command(callback: CallbackQuery):
    lst = callback.data.split('_')
    page = int(lst[-1])
    prefix = lst[-2]
    if prefix == 'test':
        dict_or_test = lst[2]
        text = 'Выберите язык:'
    else:
        dict_or_test = 'dict'
        text = 'Вот все Ваши словари.'

    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()

    langs = sorted(list({i.language for i in data.dictionary}))
    final_langs = langs[(page - 2) * 10: (page - 1) * 10]
    amount = ceil(len(langs) / 10)

    await callback.message.edit_text(f'''
{text}
''', reply_markup=inline_dictionary_keyboard_maker(final_langs, page - 1, amount, dict_or_test))
    session.close()


@dp.callback_query(F.data.startswith('dict_'), StateFilter(FSMinput.choose_dict))
async def open_dictionary_command(callback: CallbackQuery, state: FSMContext):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()

    lang = callback.data.split('_')[-1]
    words = [(i.word, i.translated_word, i.id) for i in data.dictionary if i.language == lang]
    m = len(words)
    amount = ceil(m / 10)
    text = f'Словарь - {lexicon.languages[lang]}'
    await state.update_data(words=words, amount=amount, lang=lang, page=1, text=text)
    await callback.message.edit_text(f'''
Словарь - {lexicon.languages[lang]}
''', reply_markup=inline_words_keyboard_maker(words, 1, amount, lang))
    await state.set_state(FSMinput.word)
    session.close()


@dp.callback_query(F.data == 'next_page_words', StateFilter(FSMinput.word))
async def previous_page_words_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    await callback.message.edit_text(text=data['text'],
                                     reply_markup=inline_words_keyboard_maker(data['words'], data['page'] + 1,
                                                                              data['amount']))

    await state.update_data(page=data['page'] + 1)


@dp.callback_query(F.data == 'previous_page_words', StateFilter(FSMinput.word))
async def previous_page_words_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    await callback.message.edit_text(text=data['text'],
                                     reply_markup=inline_words_keyboard_maker(data['words'], data['page'] - 1,
                                                                              data['amount']))

    await state.update_data(page=data['page'] - 1)


@dp.callback_query(F.data.startswith('word'), StateFilter(FSMinput.word))
async def open_word_card(callback: CallbackQuery):
    word_id = int(callback.data.split('_')[-1])

    session = db_session.create_session()
    data = session.query(DictionaryORM).filter(DictionaryORM.id == word_id).one()

    audio_file = text_to_audio(data.translated_word, data.language)

    await callback.message.delete()
    await callback.message.answer_audio(audio=FSInputFile("audio.mp3"), caption=f'''
{data.word} - {data.translated_word}
''', reply_markup=inline_word_keyboard_maker(data.id))
    session.close()
    os.remove(audio_file)


@dp.callback_query(F.data.startswith('delete_word'), StateFilter(FSMinput.word))
async def delete_word(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    word_id = int(callback.data.split('_')[-1])
    session = db_session.create_session()
    data = session.query(DictionaryORM).filter(DictionaryORM.id == word_id).one()
    session.delete(data)
    session.commit()

    await callback.message.delete()
    await callback.message.answer('''
Слово удалено.
''')
    await callback.answer(reply_markup=keyboard_menu)
    session.close()


@dp.callback_query(F.data == 'choose_language', StateFilter(FSMinput.word))
@dp.callback_query(F.data == 'choose_language', StateFilter(FSMinput.choose_dict))
async def choose_language_add_word_command(callback: CallbackQuery, state: FSMContext):
    amount = ceil(len(lexicon.languages.keys()) / 10)

    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(list(lexicon.languages.keys())[:10], 1, amount, 'lang'))
    await state.set_state(FSMinput.choose_lang)


@dp.callback_query(F.data.startswith('next_page_phrase_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('next_page_picture_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('next_page_audio_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('next_page_lang'), StateFilter(FSMinput.choose_lang))
async def next_page_lang_command(callback: CallbackQuery):
    lst = callback.data.split('_')
    page = int(lst[-1])
    type = lst[2] + '_' + lst[3]
    if callback.data.startswith('next_page_audio_test'):
        amount = ceil(len(lexicon.languages_for_audio.keys()) / 10)
        type += '_' + lst[4]
        if page * 10 >= len(lexicon.languages.keys()):
            items = list(lexicon.languages_for_audio.keys())[page * 10:]
        else:
            items = list(lexicon.languages_for_audio.keys())[page * 10: (page + 1) * 10]
    else:
        amount = ceil(len(lexicon.languages.keys()) / 10)
        if page * 10 >= len(lexicon.languages.keys()):
            items = list(lexicon.languages.keys())[page * 10:]
        else:
            items = list(lexicon.languages.keys())[page * 10: (page + 1) * 10]
    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(items, page + 1, amount, type))


@dp.callback_query(F.data.startswith('previous_page_phrase_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('previous_page_picture_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('previous_page_audio_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('previous_page_lang'), StateFilter(FSMinput.choose_lang))
async def previous_page_lang_command(callback: CallbackQuery):
    lst = callback.data.split('_')
    page = int(lst[-1])
    type = lst[2] + '_' + lst[3]
    if callback.data.startswith('previous_page_audio_test'):
        amount = ceil(len(lexicon.languages_for_audio.keys()) / 10)
        items = list(lexicon.languages_for_audio.keys())[(page - 2) * 10: (page - 1) * 10]
        type += '_' + lst[4]
    else:
        amount = ceil(len(lexicon.languages.keys()) / 10)
        items = list(lexicon.languages.keys())[(page - 2) * 10: (page - 1) * 10]
    await callback.message.edit_text('''
Какой язык ?
''', reply_markup=inline_language_keyboard_maker(items, page - 1, amount, type))


@dp.callback_query(F.data.startswith('choose_language_'), StateFilter(FSMinput.word))
@dp.callback_query(F.data.startswith('lang_'), StateFilter(FSMinput.choose_lang))
async def choose_language_dictionary_command(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language=callback.data.split('_')[-1])
    await callback.message.edit_text('''
Что за слово ?
''')
    await state.set_state(FSMinput.real_add_word)


@dp.message(F.text, DigitFilter(), SpecialCharactersFilter(special_symbols), EmojiFilter(),
            StateFilter(FSMinput.real_add_word))
async def word_is_added_to_the_dictionary(message: Message, state: FSMContext):
    lang = await state.get_data()
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
    language = lang['language']
    word = message.text
    translated_word = translate(word, language)
    data = DictionaryORM(
        user_id=user.id,
        language=language,
        word=word,
        translated_word=translated_word
    )
    user.dictionary.append(data)
    session.add(user)
    session.commit()

    await message.answer(f'''
{word} - {translated_word}
Ваше слово занесено в словарь.
''', reply_markup=keyboard_menu)
    await state.clear()
    session.close()


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
    langs = sorted(set([i.language for i in user.statistics]))
    await state.update_data(languages=langs)
    m = len(langs)
    amount = ceil(m / 10)
    amount = 1 if amount == 0 else amount
    await message.answer('''
Выберите язык, по которому хотите посмотреть результаты:
''', reply_markup=inline_language_keyboard_maker(langs, 1, amount, 'lang'))
    await state.set_state(FSMinput.result_lang)
    session.close()


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
''', reply_markup=inline_language_keyboard_maker(items, page + 1, amount, 'lang'))


@dp.callback_query(F.data.startswith('previous_page_lang'), StateFilter(FSMinput.result_lang))
async def previous_page_lang_result_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    amount = ceil(len(data['languages']) / 10)

    page = int(callback.data.lstrip('previous_page_lang'))

    items = data['languages'][(page - 2) * 10: (page - 1) * 10]

    await callback.message.edit_text('''
Выберите язык, по которому хотите посмотреть результаты:
''', reply_markup=inline_language_keyboard_maker(items, page - 1, amount, 'lang'))


@dp.callback_query(F.data.startswith('lang_'), StateFilter(FSMinput.result_lang))
async def check_results_of_tests(callback: CallbackQuery, state: FSMContext):
    language = callback.data.split('_')[-1]
    session = db_session.create_session()
    user = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    grades = sorted([(int(i.type_of_tests), i.result) for i in user.statistics if i.language == language],
                    key=lambda x: x[0])
    text = ''
    for i in grades:
        if i[0] == 1:
            text += f'Индивидуальный - {i[1]:.2f}\n'
        if i[0] == 2:
            text += f'Системный - {i[1]:.2f}\n'
        if i[0] == 3:
            text += f'По картинкам - {i[1]:.2f}\n'
        if i[0] == 4:
            text += f'Аудио - {i[1]:.2f}\n'

    await callback.message.edit_text(f'''
Вот Ваши оценки по языку {lexicon.languages[language]}:
{text}
''')
    await callback.answer(reply_markup=keyboard_menu)
    await state.clear()
    session.close()


@dp.message(Command(commands=["test"]), StateFilter(default_state))
@dp.message(F.text.in_(['Пройти тест 🎓', 'пройти тест', 'Пройти тест']), StateFilter(default_state))
async def choose_type_of_test_command(message: Message, state: FSMContext):
    await message.answer('''
Выберите тип тестирования:
''', reply_markup=inline_tests_keyboard_maker())
    await state.set_state(FSMinput.start_test)


@dp.callback_query(F.data == 'word_test', StateFilter(FSMinput.start_test))
async def choose_language_for_word_test_command(callback: CallbackQuery, state: FSMContext):
    session = db_session.create_session()
    data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
    all_langs = [i.language for i in data.dictionary]
    langs = sorted({i for i in all_langs if all_langs.count(i) >= 10})
    type = callback.data
    if langs:
        m = len(langs)
        amount = ceil(m / 10)
        n = m if m < 10 else 10
        await callback.message.edit_text(f'''
Выберите язык:
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount, type))
        await state.set_state(FSMinput.choose_dict)
    else:
        await callback.message.edit_text(f'''
У Вас нет словарей, по которым можно составить тест.
''', reply_markup=new_dictionary)
        await state.set_state(FSMinput.word)
    session.close()


@dp.callback_query(F.data.startswith('audio_test_0'), StateFilter(FSMinput.test))
async def choose_individual_audio_test_type(callback: CallbackQuery, state: FSMContext):
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
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount, 'audio_test_0'))
        await state.set_state(FSMinput.audio_test)
    else:
        await callback.message.edit_text(f'''
У Вас нет словарей, по которым можно составить тест.
''', reply_markup=new_dictionary)
        await state.set_state(FSMinput.word)


@dp.callback_query(F.data.startswith('audio_test'), StateFilter(FSMinput.test))
@dp.callback_query(F.data.in_(['phrase_test', 'picture_test']), StateFilter(FSMinput.start_test))
async def choose_language_for_other_tests_command(callback: CallbackQuery, state: FSMContext):
    if callback.data.startswith('audio_test'):
        langs = list(lexicon.languages_for_audio.keys())
    else:
        langs = list(lexicon.languages.keys())
    m = len(langs)
    amount = ceil(m / 10)
    n = m if m < 10 else 10
    type = callback.data
    await callback.message.edit_text('''
Выберите язык:
''', reply_markup=inline_dictionary_keyboard_maker(langs[:n], 1, amount, type))
    await state.set_state(FSMinput.choose_dict)


@dp.callback_query(F.data.startswith('picture_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data.startswith('phrase_test'), StateFilter(FSMinput.choose_dict))
@dp.callback_query(F.data == 'audio_test', StateFilter(FSMinput.start_test))
async def word_test_running(callback: CallbackQuery, state: FSMContext):
    lst = callback.data.split('_')
    language = lst[-1]
    type = lst[0]
    session = db_session.create_session()
    data, text = [], ''
    groups = set()
    if type == 'phrase':
        data = session.query(SystemInfoORM).all()
        text = 'фраз'
    elif type == 'picture':
        data = session.query(PictureInfoORM).all()
        text = 'картинок'
    elif type == 'audio':
        data = session.query(SystemInfoORM).all()
        text = 'аудио'
        groups.add('0')
    session.close()

    for i in data:
        groups.add(i.group)

    await callback.message.edit_text(f'''
Выберите группу {text}:
''', reply_markup=inline_phrase_audio_picture_test_group_keyboard_maker(language, groups, type))
    await state.set_state(FSMinput.test)


@dp.callback_query(F.data.startswith('picture_test'), StateFilter(FSMinput.test))
async def picture_test_running(callback: CallbackQuery, state: FSMContext):
    lst = callback.data.split('_')
    language = lst[-1]
    type = lst[0]
    n, rating, info, mistakes = 0, 0, [], []
    session = db_session.create_session()
    data = session.query(PictureInfoORM).filter(PictureInfoORM.group == lst[-2]).all()
    info = [(i.what, translate(i.what, language), i.picture) for i in data]
    shuffle(info)
    info = info[:10]
    text = '\n'.join([f'{i[0]} - {i[1]}' for i in info])
    shuffle(info)
    session.close()
    photo_file = FSInputFile(info[0][-1])
    await callback.message.edit_text(f'''
{text}
''')
    time.sleep(10)
    await callback.message.delete()
    await callback.message.answer(text='Что изображено на картинке ?')
    await callback.message.answer_photo(photo=photo_file,
                                        reply_markup=inline_word_test_answer_keyboard_maker([i[1] for i in info], n,
                                                                                            type))
    await state.set_state(FSMinput.test)
    await state.update_data(language=language, info=info, n=n, rating=rating, mistakes=mistakes)


@dp.callback_query(F.data.startswith('phrase_test'), StateFilter(FSMinput.test))
@dp.callback_query(F.data.startswith('word_test'), StateFilter(FSMinput.choose_dict))
async def word_or_phrase_test_running(callback: CallbackQuery, state: FSMContext):
    lst = callback.data.split('_')
    language = lst[-1]
    type = lst[0]
    n, rating, info, mistakes = 0, 0, [], []
    session = db_session.create_session()
    if type == 'word':
        data = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
        info = [(i.word, i.translated_word) for i in data.dictionary if i.language == language]
        shuffle(info)
        info = info[:10]
    elif type == 'phrase':
        data = session.query(SystemInfoORM).filter(SystemInfoORM.group == lst[-2]).all()
        info = [(i.phrase, translate(i.phrase, language)) for i in data]
        shuffle(info)
        info = info[:10]
    text = '\n'.join([f'{i[0]} - {i[1]}' for i in info])
    shuffle(info)
    await callback.message.edit_text(f'''
{text}
''')
    time.sleep(10)
    await callback.message.edit_text(f'''
Как переводится это:
{info[n][0]}
''', reply_markup=inline_word_test_answer_keyboard_maker([i[1] for i in info], n, type))
    await state.set_state(FSMinput.test)
    await state.update_data(language=language, info=info, n=n, rating=rating, mistakes=mistakes)
    session.close()


@dp.callback_query(F.data.startswith('picture_answer'), StateFilter(FSMinput.test))
@dp.callback_query(F.data.startswith('phrase_answer'), StateFilter(FSMinput.test))
@dp.callback_query(F.data.startswith('word_answer'), StateFilter(FSMinput.test))
async def test_answering(callback: CallbackQuery, state: FSMContext):
    info = await state.get_data()
    lst = callback.data.split('_')
    type = {'word': '1', 'phrase': '2', 'picture': '3'}[lst[0]]

    if lst[-1] == 'true':
        info['rating'] += 1
    else:
        info['mistakes'].append(info['n'])

    if type == '3':
        await callback.message.edit_caption(caption=f"Правильный ответ:\n{info['info'][info['n']][1]} - {info['info'][info['n']][0]}")
    else:
        await callback.message.edit_text(f"Правильный ответ:\n{info['info'][info['n']][1]} - {info['info'][info['n']][0]}")
    time.sleep(3)

    info['n'] += 1
    grade = calculate_grade(info['rating'])

    await state.update_data(n=info['n'], rating=info['rating'], mistakes=info['mistakes'])

    if info['n'] == 10:
        text_mistakes = ''
        if info['mistakes']:
            text = '\n'.join([f"{info['info'][i][1]} - {info['info'][i][0]}" for i in info['mistakes']])
            text_mistakes = f'\nСлучаи, где Вы допустили ошибку:\n{text}'

        if type == '3':
            await callback.message.delete()
            await callback.message.answer(text=f'''
Ты прошёл тест.
Твой результат: {info['rating']}/10
Это {grade}{text_mistakes}
''')
        else:
            await callback.message.edit_text(f'''
Ты прошёл тест.
Твой результат: {info['rating']}/10
Это {grade}{text_mistakes}
''')
        await callback.answer(reply_markup=keyboard_menu)

        session = db_session.create_session()
        user = session.query(UserORM).filter(UserORM.tg_id == callback.model_dump()['from_user']['id']).one()
        stat = [i for i in user.statistics if i.language == info['language'] and i.type_of_tests == type]
        if stat:
            stat[0].number_of_attempts += 1
            stat[0].result = (stat[0].result * (stat[0].number_of_attempts - 1) + grade) / stat[0].number_of_attempts
        else:
            data = ResultsORM(
                user_id=user.id,
                language=info['language'],
                type_of_tests=type,
                result=grade,
                number_of_attempts=1
            )
            user.statistics.append(data)
            session.add(user)
        session.commit()
        await state.clear()
        session.close()
    else:
        if type == '3':
            photo_file = InputMediaPhoto(media=FSInputFile(info['info'][info['n']][-1]))
            await callback.message.edit_media(media=photo_file, reply_markup=inline_word_test_answer_keyboard_maker(
                [i[1] for i in info['info']], info['n'], lst[0]))
        else:
            await callback.message.edit_text(f'''
Как переводится это:
{info['info'][info['n']][0]}
''', reply_markup=inline_word_test_answer_keyboard_maker([i[1] for i in info['info']], info['n'], lst[0]))


@dp.callback_query(F.data.startswith('audio_test'), StateFilter(FSMinput.choose_dict))
async def choose_audio_test_type(callback: CallbackQuery, state: FSMContext):
    lst = callback.data.split('_')
    language = lst[-1]
    session = db_session.create_session()
    n, rating, info = 0, 0, []
    data = session.query(SystemInfoORM).filter(SystemInfoORM.group == lst[-2]).all()
    info = [(i.phrase, translate(i.phrase, language)) for i in data]
    shuffle(info)
    info = info[:10]
    audio_file = text_to_audio(info[0][1], language)

    await callback.message.delete()
    await callback.message.answer_audio(audio=FSInputFile(audio_file), caption=f'''
Повторите
Перевод: {info[0][0]}
''')
    await state.set_state(FSMinput.audio_test)
    await state.update_data(language=language, info=info, n=n, rating=rating)
    os.remove(audio_file)
    session.close()


@dp.callback_query(F.data.startswith('audio_test_0'), StateFilter(FSMinput.audio_test))
async def audio_test_0_before_answering(callback: CallbackQuery, state: FSMContext):
    lst = callback.data.split('_')
    language = lst[-1]
    session = db_session.create_session()
    n, rating, info, mistakes = 0, 0, [], []
    data = session.query(DictionaryORM).filter(DictionaryORM.language == language).all()
    info = [(i.word, i.translated_word) for i in data]
    shuffle(info)
    info = info[:10]
    audio_file = text_to_audio(info[0][1], language)

    await callback.message.delete()
    await callback.message.answer_audio(audio=FSInputFile(audio_file), caption=f'''
Повторите. 
Перевод: {info[0][0]}
''')
    await state.set_state(FSMinput.audio_test)
    await state.update_data(language=language, info=info, n=n, rating=rating)
    os.remove(audio_file)
    session.close()


@dp.message(F.content_type.in_({'audio', 'voice'}), StateFilter(FSMinput.audio_test))
async def audio_test_answering(message: Message, state: FSMContext):
    info = await state.get_data()
    rate = 0

    recognizer = sr.Recognizer()
    user_audio_path = os.path.join(TEMP_PATH, f"{message.message_id}.ogg")
    processed_audio_path = os.path.splitext(user_audio_path)[0] + "_processed.wav"
    word = info['info'][info['n']][1]
    audio_file = os.path.join(TEMP_PATH, f"{normalize_text(word)}.mp3")

    tts = gTTS(word, lang=info['language'])
    tts.save(audio_file)

    info['n'] += 1

    file_info = await bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as response:
            if response.status == 200:
                async with aiofiles.open(user_audio_path, 'wb') as f:
                    await f.write(await response.read())
            else:
                raise Exception(f"Ошибка загрузки файла, статус: {response.status}")

    preprocess_audio(user_audio_path, processed_audio_path)
    user_text = ''
    with sr.AudioFile(processed_audio_path) as source:
        audio = recognizer.record(source)
        try:
            user_text = recognizer.recognize_google(audio, language=lexicon.speaking_languages[lexicon.languages[info['language']]])
        except sr.UnknownValueError:
            await message.reply("""
Аудиозапись не читаема. Требования к аудиозаписи:
- Отсутствие шума
- Длительность больше секунды, но меньше пяти
- Разборчивая речь
""")
    original_word = word

    if is_similar(user_text, original_word):
        await message.reply("Совпадение найдено! Голосовое сообщение похоже на слово.")
        rate = 1
    else:
        await message.reply(f"Не совпадает. Ты сказал: '{user_text}', а должно быть: '{original_word}'.")

    for path in Path('temp_audio/').glob('*'):
        if path.is_dir():
            rmtree(path)
        else:
            path.unlink()

    info['rating'] += rate

    await state.update_data(n=info['n'], rating=info['rating'])

    if info['n'] == 10:
        grade = calculate_grade(info['rating'])
        await message.answer(f'''
Ты прошёл тест.
Твой результат: {info['rating']}/10
Это {grade}
''')

        session = db_session.create_session()
        user = session.query(UserORM).filter(UserORM.tg_id == message.model_dump()['from_user']['id']).one()
        stat = [i for i in user.statistics if i.language == info['language'] and i.type_of_tests == '4']
        if stat:
            stat[0].number_of_attempts += 1
            stat[0].result = (stat[0].result * (stat[0].number_of_attempts - 1) + grade) / stat[0].number_of_attempts
        else:
            data = ResultsORM(
                user_id=user.id,
                language=info['language'],
                type_of_tests='4',
                result=grade,
                number_of_attempts=1
            )
            user.statistics.append(data)
            session.add(user)
        session.commit()
        await state.clear()
        session.close()
    else:
        audio_file = text_to_audio(info['info'][info['n']][1], info['language'])
        await message.answer_audio(audio=FSInputFile(audio_file), caption=f'''
Повторите.
Перевод: {info['info'][info['n']][0]}
''')


if __name__ == '__main__':
    db_session.global_init('database/langdict.sqlite')
    dp.run_polling(bot)
