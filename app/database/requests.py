from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.database.models import Category, Transaction, User, async_session
from app.utils import (MAX_AMOUNT, MAX_CATEGORY_NAME, TWO_PLACES,
                       parse_amount)

CATEGORY_TYPES = ("expense", "income")
ZERO = Decimal("0.00")

# Эти категории создаются один раз при первом /start, чтобы бот был
# работоспособен сразу после запуска.
DEFAULT_CATEGORIES = {
    "expense": ("Еда", "Транспорт", "Жильё", "Здоровье", "Развлечения", "Другое"),
    "income": ("Зарплата", "Фриланс", "Подарки", "Другое"),
}


async def ensure_user(tg_id: int) -> tuple[User, bool]:
    """Возвращает пользователя и признак того, что он создан только что."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            return user, False

        user = User(tg_id=tg_id)
        session.add(user)
        await session.flush()

        session.add_all(
            Category(name=name, type=category_type, user_id=user.id)
            for category_type, names in DEFAULT_CATEGORIES.items()
            for name in names
        )
        await session.commit()
        return user, True


async def add_category(tg_id: int, name: str, category_type: str) -> Category | None:
    name = (name or "").strip()

    if not name or len(name) > MAX_CATEGORY_NAME:
        return None
    if category_type not in CATEGORY_TYPES:
        return None

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None

        # Сравниваем без учёта регистра и лишних пробелов: «Еда» и «еда»
        # для пользователя одна и та же категория. lower() в SQLite не
        # работает с кириллицей, поэтому сравниваем в Python.
        existing = await session.scalars(
            select(Category).where(
                Category.user_id == user.id,
                Category.type == category_type,
            )
        )
        if name.casefold() in {category.name.strip().casefold() for category in existing}:
            return None

        category = Category(name=name, type=category_type, user_id=user.id)
        session.add(category)
        try:
            await session.commit()
        except IntegrityError:
            # Гонка двух одинаковых запросов: уникальный индекс не дал
            # создать дубль.
            await session.rollback()
            return None

        return category


async def get_categories_with_counts(tg_id: int) -> list[tuple[Category, int]]:
    """Категории пользователя вместе с количеством операций в каждой."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return []

        rows = await session.execute(
            select(Category, func.count(Transaction.id))
            .outerjoin(Transaction, Transaction.category_id == Category.id)
            .where(Category.user_id == user.id)
            .group_by(Category.id)
            .order_by(Category.type, Category.id)
        )
        return list(rows.all())


def missing_default_count(categories: list[Category]) -> int:
    """Сколько базовых категорий у пользователя ещё нет."""
    existing = {(category.name.strip().casefold(), category.type) for category in categories}
    return sum(
        1
        for category_type, names in DEFAULT_CATEGORIES.items()
        for name in names
        if (name.casefold(), category_type) not in existing
    )


async def add_missing_defaults(tg_id: int) -> int:
    """Добавляет недостающие базовые категории. Возвращает их количество."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return 0

        existing = await session.scalars(
            select(Category).where(Category.user_id == user.id)
        )
        existing_keys = {
            (category.name.strip().casefold(), category.type) for category in existing
        }

        new_categories = [
            Category(name=name, type=category_type, user_id=user.id)
            for category_type, names in DEFAULT_CATEGORIES.items()
            for name in names
            if (name.casefold(), category_type) not in existing_keys
        ]
        if not new_categories:
            return 0

        session.add_all(new_categories)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return 0

        return len(new_categories)


async def count_category_transactions(tg_id: int, category_id: int) -> int:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return 0

        count = await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == user.id,
                Transaction.category_id == category_id,
            )
        )
        return count or 0


async def delete_category(tg_id: int, category_id: int) -> int | None:
    """Удаляет категорию и её операции.

    Возвращает количество удалённых операций или None, если категория не
    найдена. Операции удаляются вручную: внешний ключ старых баз не умеет
    ON DELETE CASCADE.
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None

        category = await session.scalar(
            select(Category).where(
                Category.id == category_id,
                Category.user_id == user.id,
            )
        )
        if not category:
            return None

        transactions_count = await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.category_id == category.id
            )
        )

        await session.execute(
            delete(Transaction).where(Transaction.category_id == category.id)
        )
        await session.delete(category)
        await session.commit()
        return transactions_count or 0


async def add_transaction(
    tg_id: int,
    category_id: int,
    amount: Decimal,
    category_type: str,
) -> Transaction | None:
    amount = parse_amount(str(amount))
    if amount is None or amount <= 0 or amount > MAX_AMOUNT:
        return None
    if category_type not in CATEGORY_TYPES:
        return None

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None

        category = await session.scalar(
            select(Category).where(
                Category.user_id == user.id,
                Category.id == category_id,
            )
        )
        # Категория должна принадлежать пользователю и совпадать по типу:
        # нельзя записать расход в доходную категорию.
        if not category or category.type != category_type:
            return None

        transaction = Transaction(
            user_id=user.id,
            category_id=category.id,
            amount=amount,
            type=category.type,
        )
        session.add(transaction)
        await session.commit()
        return transaction


async def get_categories_by_user_and_type(tg_id: int, category_type: str) -> list[Category]:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return []

        result = await session.scalars(
            select(Category)
            .where(
                Category.user_id == user.id,
                Category.type == category_type,
            )
            .order_by(Category.id)
        )
        return list(result.all())


async def get_category(tg_id: int, category_id: int) -> Category | None:
    async with async_session() as session:
        return await session.scalar(
            select(Category)
            .join(User, Category.user_id == User.id)
            .where(
                User.tg_id == tg_id,
                Category.id == category_id,
            )
        )


def _period_start(period: str) -> datetime | None:
    now = datetime.now()

    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


async def get_stats(tg_id: int, period: str) -> tuple[Decimal, Decimal]:
    """Возвращает (доходы, расходы) за период."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return ZERO, ZERO

        start = _period_start(period)

        query = (
            select(Transaction.type, func.sum(Transaction.amount))
            .where(Transaction.user_id == user.id)
            .group_by(Transaction.type)
        )
        if start is not None:
            query = query.where(Transaction.date >= start)

        rows = (await session.execute(query)).all()
        totals = {
            transaction_type: Decimal(str(total or 0)).quantize(TWO_PLACES)
            for transaction_type, total in rows
        }

        return totals.get("income", ZERO), totals.get("expense", ZERO)
