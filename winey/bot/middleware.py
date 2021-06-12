import logging
from aiogram import types
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.dispatcher.middlewares import BaseMiddleware, LifetimeControllerMiddleware
from aiogram.dispatcher.handler import CancelHandler
from winey.db.models import User
from winey.db import OrmSession


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class PrivateChatOnlyMiddleware(BaseMiddleware):

    async def on_pre_process_message(self, message: types.Message, data: dict):
        flt = ChatTypeFilter(types.ChatType.PRIVATE)
        if not await flt.check(message):
            log.info(f"Handling message with id:{message.message_id} "
                     f"in chat [{message.chat.type}:{message.chat.id}] cancelled")
            raise CancelHandler()


class GetOrCreateUserMiddleware(LifetimeControllerMiddleware):
    skip_patterns = ['error', 'update', 'channel_post', 'poll']

    async def pre_process(self, obj, data, *args):
        from_user = types.User.get_current()
        async with OrmSession() as session:
            # TODO take care about caching
            user = await session.get(User, from_user.id)
            data['user'] = user
            data['is_new_user'] = False
            if not data['user']:
                dt = obj.date
                log.info(f'Creating user @{from_user.username} with id {from_user.id}')
                user = User(
                    id=from_user.id,
                    username=from_user.username,
                    first_name=from_user.first_name,
                    last_name=from_user.last_name,
                    lang=from_user.language_code,
                    joined_dt=dt
                )
                session.add(user)
                await session.commit()
                data['user'] = user
                data['is_new_user'] = True
