import logging
from aiogram import types
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.dispatcher.middlewares import BaseMiddleware, LifetimeControllerMiddleware
from aiogram.dispatcher.handler import CancelHandler
from wine_log.db.models import User
from wine_log.db import OrmSession


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class PrivateChatOnlyMiddleware(BaseMiddleware):

    async def on_pre_process_message(self, message: types.Message, data: dict):
        flt = ChatTypeFilter(types.ChatType.PRIVATE)
        if not await flt.check(message):
            log.info(f"Handling message with id:{message.message_id} "
                     f"in chat [{message.chat.type}:{message.chat.id}] cancelled")
            raise CancelHandler()


class GetUserMiddleware(LifetimeControllerMiddleware):
    skip_patterns = ['error', 'update', 'channel_post', 'poll']

    async def pre_process(self, obj, data, *args):
        sender = obj.from_user
        async with OrmSession() as session:
            # TODO take care about caching
            user = await session.get(User, sender['id'])
            data['user'] = user
            data['is_new_user'] = user is None


class RegisterUserMiddleware(LifetimeControllerMiddleware):
    skip_patterns = ['error', 'update', 'channel_post', 'poll']

    async def pre_process(self, obj, data, *args):
        sender = obj.from_user
        dt = obj.date
        if not data['user']:
            log.info(f'Creating user @{sender.username} with id {sender.id}')
            async with OrmSession() as session:
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
                data['user'] = user
