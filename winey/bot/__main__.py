import logging
import os
from datetime import datetime
import asyncio
import io
import boto3
from concurrent.futures import ThreadPoolExecutor
import aiogram.utils.markdown as md
from aiogram.utils.emoji import emojize
from aiogram.utils.text_decorations import markdown_decoration
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.fsm_storage.files import PickleStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from .middleware import PrivateChatOnlyMiddleware, GetOrCreateUserMiddleware
from winey.db import OrmSession
from winey.db.models import User, TastingRecord, WinePhoto


logging.basicConfig(level=logging.INFO)
log = logging.getLogger('winey.bot')
API_TOKEN = os.environ['WINEY_BOT_TOKEN']
bot = Bot(token=API_TOKEN)

storage_file_path = os.environ.get('WINEY_STATE_STORAGE_FILE_PATH')
if storage_file_path:
    storage = PickleStorage(storage_file_path)
else:
    storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

s3 = boto3.resource('s3', endpoint_url=os.environ['WINEY_S3_ENDPOINT_URL'])
s3bucket = s3.Bucket(os.environ['WINEY_S3_WINE_PHOTOS_BUCKET'])
pool = ThreadPoolExecutor()


# States
class Form(StatesGroup):
    photo = State()
    wine_name = State()
    region = State()
    grapes = State()
    vintage_year = State()
    experience = State()


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message, user: User, is_new_user: bool):
    """
    Conversation's entry point
    """
    if is_new_user:
        await message.answer(
            emojize(md.text(
                md.text('Привет, меня зовут Уайни.'),
                md.text('Позовите меня с помощью команды /newrecord, '
                        'когда в следующий раз будете хорошо проводить время за бокалом вина.'),
                md.text('Я помогу вам запомнить, что это было за вино и какие ощущения у вас были по этому поводу, '
                        'а от вас протребуется только:'),
                md.text(':camera_with_flash: Сфотографировать этикетку'),
                md.text(':grapes: Сообщить название вина, регион его происхождения, сортовой состав и год урожая'),
                md.text(':wine_glass: В свободной форме рассказать о собственных ощущениях, ассоциациях... '
                        'Все, что приходит на ум'),
                md.text(''),
                md.text('Пришлите команду /cancel или одно слово "Отмена", если передумали что-либо записывать.'),
                md.text(''),
                md.text('Ну и заходите как-нибудь ко мне на сайт -',
                        markdown_decoration.link('winey.fun', 'https://winey.fun')),
                sep='\n',
            )),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await message.answer(f'Привет, {user.first_name}, приятно получать от вас новые сообщения. '
                             'Я пока умею не так уж много чего, но могу рассказать с помощью команды /help.')


@dp.message_handler(commands='help')
async def cmd_help(message: types.Message):
    await message.answer(
        emojize(md.text(
            md.text('Мое имя Уайни. И вот, что я умею:'),
            md.text(''),
            md.text('/newrecord - с помощью этой команды я помогу вам запомнить, '
                    'что это было за вино и какие ощущения у вас были по этому поводу'),
            md.text('В ответ я попрошу:'),
            md.text(':camera_with_flash: Сфотографировать этикетку'),
            md.text(':grapes: Сообщить название вина, регион его происхождения, сортовой состав и год урожая'),
            md.text(':wine_glass: В свободной форме рассказать о собственных ощущениях, ассоциациях... '
                    'Все, что приходит на ум'),
            md.text(''),
            md.text('/cancel или одно слово "Отмена" - так можно мне сообщить, если передумали что-либо записывать.'),
            md.text(''),
            md.text('Мой сайт -', markdown_decoration.link('winey.fun', 'https://winey.fun')),
            sep='\n',
        )),
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message_handler(commands='newrecord')
async def cmd_newrecord(message: types.Message):
    """
    Conversation's entry point
    """
    await Form.photo.set()
    await message.reply('Сфотографируйте, пожалуйста, бутылку, чтобы была видна этикетка')


@dp.message_handler(commands='cancel', state='*')
@dp.message_handler(Text(equals='отмена', ignore_case=True), state='*')
async def cancel_newrecord(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer('В данный момент вы ничего не просили записывать')
    else:
        await state.finish()
        await message.reply('Ладно, не в этот раз')


@dp.message_handler(content_types=types.ContentTypes.PHOTO, state=Form.photo)
async def process_photo(message: types.Message, state: FSMContext):
    dt = message.date
    largest_index = message.photo.index(max(message.photo, key=lambda photo: photo.width))
    await state.update_data(
        photo_file_id=message.photo[largest_index].file_id,
        s3_obj_key=f'{dt.year}{str(dt.month).rjust(2, "0")}{str(dt.day).rjust(2, "0")}_'
                   f'{str(dt.hour).rjust(2, "0")}{str(dt.minute).rjust(2, "0")}{str(dt.second).rjust(2, "0")}_'
                   f'{message.photo[largest_index].file_unique_id}'
    )
    await Form.next()
    await message.reply('Как называется вино?')


@dp.message_handler(content_types=types.ContentTypes.TEXT, state=Form.wine_name)
async def process_wine_name(message: types.Message, state: FSMContext):
    await state.update_data(wine_name=message.text)
    await Form.next()
    await message.reply('Какой у него регион происхождения?')


@dp.message_handler(content_types=types.ContentTypes.TEXT, state=Form.region)
async def process_region(message: types.Message, state: FSMContext):
    await state.update_data(region=message.text)
    await Form.next()
    await message.reply('Из каких сортов винограда оно сделано?')


@dp.message_handler(content_types=types.ContentTypes.TEXT, state=Form.grapes)
async def process_grapes(message: types.Message, state: FSMContext):
    await state.update_data(grapes=message.text)
    await Form.next()
    await message.reply('Из винограда какого года урожая оно сделано? '
                        'В сообщении должны быть только цифры, либо пришлите дефис, если информации нет')


@dp.message_handler(Text(equals='-', ignore_case=True), state=Form.vintage_year)
async def process_empty_vintage_year(message: types.Message):
    await Form.next()
    await message.reply('Наконец, какие ваши ощущения? Пишите свободно.')


@dp.message_handler(lambda message: message.text.isdigit(), state=Form.vintage_year)
async def process_vintage_year(message: types.Message, state: FSMContext):
    year = int(message.text)
    current_year = datetime.now().year
    if year > current_year:
        await message.reply(f'На дворе {current_year}, а вы написали {year}... '
                            'Что-то здесь не так, повторите, пожалуйста')
    else:
        await state.update_data(vintage_year=year)
        await Form.next()
        await message.reply('Наконец, какие ваши ощущения? Пишите свободно.')


@dp.message_handler(lambda message: not message.text.isdigit() and message.text != '-', state=Form.vintage_year)
async def process_vintage_year_invalid(message: types.Message):
    await message.reply('Извините, в сообщении должны быть только цифры, либо пришлите дефис, если информации нет')


@dp.message_handler(content_types=types.ContentTypes.TEXT, state=Form.experience)
async def process_experience(message: types.Message, state: FSMContext):
    sender = message.from_user
    dt = message.date
    async with state.proxy() as data:
        data['experience'] = message.text

        log.info(f'Getting file {data["photo_file_id"]} and downloading it to memory buffer')
        file = await bot.get_file(data['photo_file_id'])
        file_buf = io.BytesIO()
        await file.download(file_buf)

        log.info(f'Put file {data["photo_file_id"]} to s3 with key {data["s3_obj_key"]}')
        future = pool.submit(s3bucket.put_object, Key=data['s3_obj_key'], Body=file_buf)
        await asyncio.wrap_future(future)

        async with OrmSession() as session:
            photo = WinePhoto(id=data['s3_obj_key'])
            tasting_record = TastingRecord(
                user_id=sender.id,
                dt=dt,
                wine_name=data['wine_name'],
                region=data['region'],
                grapes=data['grapes'],
                vintage_year=data.get('vintage_year'),
                experience=data['experience'],
            )
            tasting_record.photos.append(photo)
            session.add(tasting_record)
            await session.commit()

        await message.answer(
            md.text(
                md.text('Готово, информация в базе'),
                md.text('Для просмотра переходите на', markdown_decoration.link('winey.fun', 'https://winey.fun')),
                sep='\n',
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    await state.finish()


if __name__ == '__main__':
    dp.middleware.setup(LoggingMiddleware(log))
    dp.middleware.setup(PrivateChatOnlyMiddleware())
    dp.middleware.setup(GetOrCreateUserMiddleware())
    executor.start_polling(dp, skip_updates=True)
