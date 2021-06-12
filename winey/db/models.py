from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=False)
    username = Column(String(256))
    first_name = Column(String(256))
    last_name = Column(String(256))
    lang = Column(String(64))
    joined_dt = Column(DateTime(timezone=True), nullable=False)
    tasting_records = relationship('TastingRecord')


class TastingRecord(Base):
    __tablename__ = 'tasting_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    dt = Column(DateTime(timezone=True), nullable=False)
    wine_name = Column(String(128), nullable=False)
    region = Column(String(128), nullable=False)
    grapes = Column(String(256), nullable=False)
    vintage_year = Column(Integer)
    experience = Column(Text, nullable=False)
    photos = relationship('WinePhoto')


class WinePhoto(Base):
    __tablename__ = 'wine_photos'
    id = Column(String(128), primary_key=True)
    tasting_record_id = Column(Integer, ForeignKey('tasting_records.id'))
