import logging
from aiogram.dispatcher.middlewares import LifetimeControllerMiddleware
from wine_log.db.models import User
from wine_log.db import OrmSession


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


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
