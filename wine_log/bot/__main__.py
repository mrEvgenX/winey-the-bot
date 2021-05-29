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
from wine_log.db import OrmSession
from wine_log.db.models import User, TastingRecord, WinePhoto


logging.basicConfig(level=logging.INFO)
API_TOKEN = os.environ['WINE_LOG_BOT_TOKEN']
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
    wine_name = State()
    region = State()
    grapes = State()
    experience = State()


@dp.message_handler(chat_type=types.ChatType.PRIVATE, commands='start')
async def cmd_start(message: types.Message):
    """
    Conversation's entry point
    """
    logging.info('cmd_start')
    sender = message.from_user
    dt = message.date
    async with OrmSession() as session:
        user = await session.get(User, sender['id'])
        if not user:
            user = User(
                id=sender.id,
                username=sender.username,
                first_name=sender.first_name,
                last_name=sender.last_name,
                lang=sender.language_code,
                joined_dt=dt
            )
            session.add(user)
            await session.commit()
    await Form.photo.set()
    await message.reply("Сфотографируйте, пожалуйста, бутылку, чтобы была видна этикетка")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.PHOTO, state=Form.photo)
async def process_photo(message: types.Message, state: FSMContext):
    dt = message.date
    current_state = await state.get_state()
    logging.info('process_photo %s', current_state)

    largest_index = message.photo.index(max(message.photo, key=lambda photo: photo.width))

    await state.update_data(
        photo_file_id=message.photo[largest_index].file_id,
        s3_obj_key=f'{dt.year}{str(dt.month).rjust(2, "0")}{str(dt.day).rjust(2, "0")}_'
                   f'{str(dt.hour).rjust(2, "0")}{str(dt.minute).rjust(2, "0")}{str(dt.second).rjust(2, "0")}_'
                   f'{message.photo[largest_index].file_unique_id}'
    )
    await Form.next()
    await message.reply("Как называется вино?")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.wine_name)
async def process_wine_name(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_wine_name %s', current_state)
    await state.update_data(wine_name=message.text)
    await Form.next()
    await message.reply("Из какой оно страны?")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.region)
async def process_region(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_region %s', current_state)
    await state.update_data(region=message.text)
    await Form.next()
    await message.reply("Из каких сортов винограда оно сделано?")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.grapes)
async def process_grapes(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info('process_grapes %s', current_state)
    await state.update_data(grapes=message.text)
    await Form.next()
    await message.reply("Наконец, какие ваши ощущения? Пишите свободно.")


@dp.message_handler(chat_type=types.ChatType.PRIVATE, content_types=types.ContentTypes.TEXT, state=Form.experience)
async def process_experience(message: types.Message, state: FSMContext):
    sender = message.from_user
    dt = message.date
    current_state = await state.get_state()
    logging.info('process_experience %s', current_state)
    async with state.proxy() as data:
        data['experience'] = message.text

        file = await bot.get_file(data['photo_file_id'])
        logging.info(await file.get_url())
        file_buf = io.BytesIO()
        await file.download(file_buf)

        logging.info('s3 put_object: submitting to pool')
        future = pool.submit(s3bucket.put_object, Key=data['s3_obj_key'], Body=file_buf)
        logging.info('s3 put_object: awaiting wrapped future')
        await asyncio.wrap_future(future)

        async with OrmSession() as session:
            photo = WinePhoto(id=data['s3_obj_key'])
            tasting_record = TastingRecord(
                user_id=sender.id,
                dt=dt,
                wine_name=data['wine_name'],
                region=data['region'],
                grapes=data['grapes'],
                experience=data['experience'],
            )
            tasting_record.photos.append(photo)
            session.add(tasting_record)
            await session.commit()

        await message.answer(
            md.text(
                md.text('Готово, информация в базе'),
                sep='\n',
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    await state.finish()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
