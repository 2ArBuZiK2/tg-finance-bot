from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import (AsyncAttrs,
                                    async_sessionmaker, create_async_engine)
import datetime

engine = create_async_engine(url='sqlite+aiosqlite:///db.sqlite3')

async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger)


class Category(Base):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(25))
    type: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))


class Transaction(Base):
    __tablename__ = 'transactions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    amount: Mapped[int] = mapped_column()
    type: Mapped[str] = mapped_column(String(10))
    date: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)