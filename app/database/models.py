import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, event
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app import timeutils
from app.config import DATABASE_URL

# NullPool не кэширует соединения между вызовами. Для файловой SQLite это
# дёшево, а тестам позволяет переиспользовать один движок в разных
# event loop'ах, не получая соединение, привязанное к старому циклу.
engine = create_async_engine(DATABASE_URL, poolclass=NullPool)

async_session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite по умолчанию не проверяет внешние ключи."""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)


class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        Index('ux_categories_user_name_type', 'user_id', 'name', 'type', unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))


class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = (
        Index('ix_transactions_user_date', 'user_id', 'date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    type: Mapped[str] = mapped_column(String(10))
    date: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=timeutils.now
    )


def _create_missing_indexes(sync_connection) -> None:
    """Досоздаёт индексы для БД, созданных старой версией бота.

    create_all() не трогает уже существующие таблицы, поэтому уникальные
    индексы и индексы по датам нужно создавать отдельно.
    """
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            index.create(sync_connection, checkfirst=True)


async def async_main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_create_missing_indexes)
