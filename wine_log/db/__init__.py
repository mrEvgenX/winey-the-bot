import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


DATABASE_URI = os.environ['WINEY_DATABASE_URI']
orm_engine = create_async_engine(DATABASE_URI, echo=True)
OrmSession = sessionmaker(orm_engine, expire_on_commit=False, class_=AsyncSession)
