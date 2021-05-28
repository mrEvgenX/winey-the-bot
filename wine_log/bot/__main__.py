import logging
import os
import asyncio
import io
import boto3
from concurrent.futures import ThreadPoolExecutor
import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
# from aiogram.contrib.fsm_storage.files import JSONStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.environ['WINE_LOG_TOKEN']

bot = Bot(token=API_TOKEN)

# For example use simple MemoryStorage for Dispatcher.
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

s3 = boto3.resource('s3', endpoint_url='https://storage.yandexcloud.net')
s3bucket = s3.Bucket('evgene-petrenko-wine-bottles')
pool = ThreadPoolExecutor()


# States
class Form(StatesGroup):
    photo = State()
    name = State()
    country = State()
    kinds = State()
    experience = State()


@dp.message_handler(chat_type=types.ChatType.PRIVATE, commands='start')
async def cmd_start(message: types.Message):
    """
    Conversation's entry point
    """
    # Set state
    logging.info('cmd_start')
    await Form.photo.set()
    await message.reply("Сфотографируйте, пожалуйста, бутылку, чтобы была видна этикетка")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.PHOTO, state=Form.photo)
async def process_photo(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_photo %s', current_state)

    # TODO take the largest
    # for ps in message.photo:
    #     url = await ps.get_url()
    #     logging.info(url)

    await state.update_data(
        photo_file_id=message.photo[-1].file_id,
        photo_file_short_id=message.photo[-1].file_unique_id
    )
    await Form.next()
    await message.reply("Как называется вино?")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.name)
async def process_name(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_name %s', current_state)
    await state.update_data(name=message.text)
    await Form.next()
    await message.reply("Из какой оно страны?")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.country)
async def process_country(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_country %s', current_state)
    await state.update_data(country=message.text)
    await Form.next()
    await message.reply("Из каких сортов винограда оно сделано?")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.kinds)
async def process_kinds(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_kinds %s', current_state)
    await state.update_data(kinds=message.text)
    await Form.next()
    await message.reply("Наконец, какие ваши ощущения? Пишите свободно.")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.experience)
async def process_experience(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_experience %s', current_state)
    async with state.proxy() as data:
        data['experience'] = message.text

        file = await bot.get_file(data['photo_file_id'])
        logging.info(await file.get_url())
        file_buf = io.BytesIO()
        await file.download(file_buf)

        logging.info('s3 put_object: submitting to pool')
        future = pool.submit(s3bucket.put_object, Key=data['photo_file_id'], Body=file_buf)
        logging.info('s3 put_object: awaiting wrapped future')
        await asyncio.wrap_future(future)

        await message.answer(
            md.text(
                md.text('Готово, информация в базе'),
                md.text('Идентификатор фотографии: ', data['photo_file_id']),
                md.text('Название: ', data['name']),
                md.text('Страна: ', data['country']),
                md.text('Сортовой состав: ', data['kinds']),
                md.text('Ощущения:'),
                md.text('Ощущения: ', data['experience']),
                sep='\n',
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    await state.finish()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
