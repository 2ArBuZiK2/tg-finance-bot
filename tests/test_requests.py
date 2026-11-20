"""Тесты слоя доступа к данным: категории, операции, статистика."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.database import requests as rq
from app.database.models import Transaction, async_session

TG_ID = 100001
OTHER_TG_ID = 100002


async def make_user(tg_id: int = TG_ID) -> int:
    user, _ = await rq.ensure_user(tg_id)
    return user.id


async def category_id(name: str, category_type: str, tg_id: int = TG_ID) -> int:
    for category, _ in await rq.get_categories_with_counts(tg_id):
        if category.name == name and category.type == category_type:
            return category.id
    raise AssertionError(f"категория {name!r} ({category_type}) не найдена")


async def insert_transaction(
    user_id: int,
    category_id: int,
    amount: str,
    category_type: str,
    days_ago: int = 0,
) -> None:
    """Кладёт операцию с нужной датой: add_transaction всегда ставит now()."""
    async with async_session() as session:
        session.add(
            Transaction(
                user_id=user_id,
                category_id=category_id,
                amount=Decimal(amount),
                type=category_type,
                date=datetime.now() - timedelta(days=days_ago),
            )
        )
        await session.commit()


async def test_ensure_user_creates_default_categories() -> None:
    user, created = await rq.ensure_user(TG_ID)

    assert created is True
    items = await rq.get_categories_with_counts(TG_ID)
    assert len(items) == 10
    assert [c.name for c, _ in items if c.type == "expense"] == list(
        rq.DEFAULT_CATEGORIES["expense"]
    )
    assert [c.name for c, _ in items if c.type == "income"] == list(
        rq.DEFAULT_CATEGORIES["income"]
    )

    again, created_again = await rq.ensure_user(TG_ID)
    assert created_again is False
    assert again.id == user.id
    assert len(await rq.get_categories_with_counts(TG_ID)) == 10


async def test_add_category_rejects_case_insensitive_duplicates() -> None:
    await make_user()

    assert await rq.add_category(TG_ID, "еда", "expense") is None
    assert await rq.add_category(TG_ID, "  ЕДА  ", "expense") is None

    # В доходах то же имя — это другая категория.
    income = await rq.add_category(TG_ID, "еда", "income")
    assert income is not None
    assert await rq.add_category(TG_ID, "ЕДА", "income") is None
    assert len(await rq.get_categories_with_counts(TG_ID)) == 11


async def test_add_category_validates_input() -> None:
    await make_user()

    assert await rq.add_category(TG_ID, "", "expense") is None
    assert await rq.add_category(TG_ID, "   ", "expense") is None
    assert await rq.add_category(TG_ID, "x" * 51, "expense") is None
    assert await rq.add_category(TG_ID, "Кафе", "transfer") is None
    assert await rq.add_category(999999, "Кафе", "expense") is None

    assert await rq.add_category(TG_ID, "  Кафе  ", "expense") is not None
    names = {category.name for category, _ in await rq.get_categories_with_counts(TG_ID)}
    assert "Кафе" in names


async def test_add_missing_defaults_restores_only_missing() -> None:
    await make_user()
    food = await category_id("Еда", "expense")
    other_income = await category_id("Другое", "income")

    assert await rq.delete_category(TG_ID, food) == 0
    assert await rq.delete_category(TG_ID, other_income) == 0

    categories = [category for category, _ in await rq.get_categories_with_counts(TG_ID)]
    assert rq.missing_default_count(categories) == 2

    assert await rq.add_missing_defaults(TG_ID) == 2
    assert rq.missing_default_count(
        [category for category, _ in await rq.get_categories_with_counts(TG_ID)]
    ) == 0
    assert await rq.add_missing_defaults(TG_ID) == 0


async def test_add_transaction_validates_amount_and_type() -> None:
    await make_user()
    food = await category_id("Еда", "expense")
    salary = await category_id("Зарплата", "income")

    assert await rq.add_transaction(TG_ID, food, Decimal("100"), "income") is None
    assert await rq.add_transaction(TG_ID, food, Decimal("0"), "expense") is None
    assert await rq.add_transaction(TG_ID, food, Decimal("-1"), "expense") is None
    assert await rq.add_transaction(TG_ID, food, Decimal("1000000001"), "expense") is None
    assert await rq.add_transaction(TG_ID, 999999, Decimal("100"), "expense") is None

    transaction = await rq.add_transaction(TG_ID, food, Decimal("100"), "expense")
    assert transaction is not None
    assert transaction.amount == Decimal("100.00")
    assert transaction.type == "expense"

    income = await rq.add_transaction(TG_ID, salary, Decimal("1000"), "income")
    assert income is not None
    assert income.type == "income"


async def test_transactions_are_isolated_between_users() -> None:
    await make_user()
    await make_user(OTHER_TG_ID)

    other_food = await category_id("Еда", "expense", OTHER_TG_ID)
    assert await rq.add_transaction(TG_ID, other_food, Decimal("100"), "expense") is None

    await rq.add_transaction(OTHER_TG_ID, other_food, Decimal("100"), "expense")
    assert await rq.count_transactions(TG_ID) == 0
    assert await rq.count_transactions(OTHER_TG_ID) == 1
    assert await rq.get_stats(TG_ID, "all") == (Decimal("0.00"), Decimal("0.00"))


async def test_stats_and_category_breakdown() -> None:
    await make_user()
    food = await category_id("Еда", "expense")
    transport = await category_id("Транспорт", "expense")
    salary = await category_id("Зарплата", "income")

    await rq.add_transaction(TG_ID, food, Decimal("300"), "expense")
    await rq.add_transaction(TG_ID, transport, Decimal("100"), "expense")
    await rq.add_transaction(TG_ID, salary, Decimal("1000"), "income")

    assert await rq.get_stats(TG_ID, "all") == (Decimal("1000.00"), Decimal("400.00"))
    assert await rq.get_stats(TG_ID, "today") == (Decimal("1000.00"), Decimal("400.00"))

    breakdown = await rq.get_category_stats(TG_ID, "all")
    assert breakdown == [
        ("Зарплата", "income", Decimal("1000.00")),
        ("Еда", "expense", Decimal("300.00")),
        ("Транспорт", "expense", Decimal("100.00")),
    ]


async def test_periods_filter_old_transactions() -> None:
    user_id = await make_user()
    food = await category_id("Еда", "expense")

    await insert_transaction(user_id, food, "10", "expense", days_ago=0)
    await insert_transaction(user_id, food, "20", "expense", days_ago=3)
    await insert_transaction(user_id, food, "40", "expense", days_ago=40)

    _, today = await rq.get_stats(TG_ID, "today")
    _, week = await rq.get_stats(TG_ID, "week")
    _, month = await rq.get_stats(TG_ID, "month")
    _, all_time = await rq.get_stats(TG_ID, "all")

    assert today == Decimal("10.00")
    assert week == Decimal("30.00")
    # 40 дней назад в текущий месяц не попадают; 3 дня назад — только
    # если сегодня не 1-3 число.
    assert month in (Decimal("10.00"), Decimal("30.00"))
    assert all_time == Decimal("70.00")


async def test_history_pagination_and_deletion() -> None:
    await make_user()
    food = await category_id("Еда", "expense")

    transactions = [
        await rq.add_transaction(TG_ID, food, Decimal(str(amount)), "expense")
        for amount in range(1, 13)
    ]
    assert all(transactions)

    assert await rq.count_transactions(TG_ID) == 12

    first_page = await rq.get_transactions(TG_ID, limit=10, offset=0)
    second_page = await rq.get_transactions(TG_ID, limit=10, offset=10)
    assert len(first_page) == 10
    assert len(second_page) == 2
    assert {transaction.id for transaction, _ in first_page}.isdisjoint(
        {transaction.id for transaction, _ in second_page}
    )

    # Свежие операции идут первыми.
    assert first_page[0][0].amount == Decimal("12.00")
    assert second_page[-1][0].amount == Decimal("1.00")

    # Лимит и смещение нормализуются.
    assert len(await rq.get_transactions(TG_ID, limit=0, offset=0)) == 1
    assert len(await rq.get_transactions(TG_ID, limit=100, offset=-5)) == 12

    target = first_page[0][0].id
    found = await rq.get_transaction(TG_ID, target)
    assert found is not None
    assert found[0].id == target
    assert found[1].name == "Еда"

    assert await rq.delete_transaction(TG_ID, target) is True
    assert await rq.delete_transaction(TG_ID, target) is False
    assert await rq.count_transactions(TG_ID) == 11
    assert await rq.get_transaction(TG_ID, target) is None


async def test_delete_category_removes_its_transactions() -> None:
    await make_user()
    food = await category_id("Еда", "expense")
    await rq.add_transaction(TG_ID, food, Decimal("50"), "expense")
    await rq.add_transaction(TG_ID, food, Decimal("70"), "expense")

    assert await rq.count_category_transactions(TG_ID, food) == 2
    assert await rq.delete_category(TG_ID, food) == 2
    assert await rq.count_transactions(TG_ID) == 0
    assert await rq.get_category(TG_ID, food) is None
    assert await rq.delete_category(TG_ID, food) is None


async def test_cannot_delete_another_users_category() -> None:
    await make_user()
    await make_user(OTHER_TG_ID)
    other_food = await category_id("Еда", "expense", OTHER_TG_ID)

    assert await rq.delete_category(TG_ID, other_food) is None
    assert await rq.get_category(OTHER_TG_ID, other_food) is not None


@pytest.mark.parametrize("period", ["today", "week", "month", "all", "unknown"])
async def test_stats_for_unknown_user_are_zero(period: str) -> None:
    assert await rq.get_stats(999999, period) == (Decimal("0.00"), Decimal("0.00"))
    assert await rq.get_category_stats(999999, period) == []
