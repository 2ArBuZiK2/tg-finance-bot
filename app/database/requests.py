from app.database.models import async_session
from app.database.models import User, Category, Transaction
from sqlalchemy import select, update, delete
from sqlalchemy import func

from datetime import datetime, timedelta

async def set_user(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            session.add(User(tg_id=tg_id))
            await session.commit()


async def add_category(tg_id: int, name: str, type: str):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None

        existing = await session.scalar(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == name,
                Category.type == type
            )
        )
        if existing:
            return None

        new_category = Category(
            name=name,
            type=type,
            user_id=user.id
        )
        session.add(new_category)
        await session.commit()
        return new_category


async def add_transaction(tg_id: int, category_id: int, amount: int, type: str):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None

        category = await session.scalar(
            select(Category).where(
                Category.user_id == user.id,
                Category.id == category_id
            )
        )
        if not category:
            return None
        new_transaction = Transaction(
            user_id=user.id,
            category_id=category_id,
            amount=amount,
            type=type
        )
        session.add(new_transaction)
        await session.commit()
        return new_transaction

async def get_categories_by_user_and_type(tg_id: int, category_type: str):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return []

        result = await session.scalars(
            select(Category).where(
                Category.user_id == user.id,
                Category.type == category_type
            )
        )
        return result.all()


async def get_stats(tg_id: int, period: str):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return 0, 0

        now = datetime.now()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        elif period == "month":
            start = now - timedelta(days=30)
        else:
            start = None

        income_query = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user.id,
            Transaction.type == 'income'
        )

        if start is not None:
            income_query = income_query.where(Transaction.date >= start)

        income_sum = await session.scalar(income_query)
        income_sum = income_sum or 0

        expense_query = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user.id,
            Transaction.type == 'expense'
        )

        if start is not None:
            expense_query = expense_query.where(Transaction.date >= start)

        expense_sum = await session.scalar(expense_query)
        expense_sum = expense_sum or 0

        return income_sum, expense_sum


