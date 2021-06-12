import os
from aiohttp import web
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select
import aiohttp_jinja2
import jinja2
from winey.db.models import TastingRecord
from winey.db import OrmSession


@aiohttp_jinja2.template('index.html')
async def index(_):
    return {}


@aiohttp_jinja2.template('tasting_sessions.html')
async def handle(_):
    async with OrmSession() as session:
        select_stmt = select(TastingRecord) \
            .options(
            selectinload(TastingRecord.photos)
        ).order_by(TastingRecord.dt.desc())
        tasting_records_result = await session.execute(select_stmt)

        return {
            'tasting_records': [
                {
                    'dt': tasting_record.dt,
                    'wine_name': tasting_record.wine_name,
                    'region': tasting_record.region,
                    'grapes': tasting_record.grapes,
                    'vintage_year': tasting_record.vintage_year,
                    'experience': tasting_record.experience,
                    'photos': [
                        {
                            'id': photo.id
                         } for photo in tasting_record.photos
                    ]
                } for tasting_record in tasting_records_result.scalars()
            ],
        }


app = web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('./winey/webapp/templates'))
app.add_routes([
    web.get('/wine-log', handle),
    web.get('/', index),
])


if __name__ == '__main__':
    web.run_app(app, port=os.environ.get('WINEY_WEBAPP_PORT', 8080))
