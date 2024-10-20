from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F
from keyboards import keyboard_menu

BOT_TOKEN = 'BOT_TOKEN'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=["start"]))
async def process_start_command(message: Message):
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
    await message.answer('''
Вот Ваш словарь.
''')


@dp.message(Command(commands=["test"]))
@dp.message(F.text.in_(['Начать проверку 🎓', 'начать проверку', 'Начать проверку']))
async def start_test_command(message: Message):
    await message.answer('''
По какому языку Вы хотите начать тестирование ?    
''')


if __name__ == '__main__':
    dp.run_polling(bot)
