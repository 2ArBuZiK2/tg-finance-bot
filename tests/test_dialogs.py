"""Интеграционные тесты диалогов: хендлеры, FSM, клавиатуры."""

from decimal import Decimal

from app.database import requests as rq
from tests.support.harness import BotHarness


async def category_id(tg_id: int, name: str, category_type: str) -> int:
    for category, _ in await rq.get_categories_with_counts(tg_id):
        if category.name == name and category.type == category_type:
            return category.id
    raise AssertionError(f"категория {name!r} ({category_type}) не найдена")


def numbered_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if line.split(".", 1)[0].isdigit() and " · " in line
    ]


async def test_start_creates_default_categories_and_menu(harness: BotHarness) -> None:
    await harness.send("/start")

    assert "базовые категории" in harness.text
    assert harness.reply_keyboard == [
        "Добавить расход",
        "Добавить доход",
        "История",
        "Статистика",
        "Управление категориями",
    ]
    assert len(await rq.get_categories_with_counts(harness.tg_id)) == 10

    await harness.send("/start")
    assert "Выберите действие в меню ниже" in harness.text
    assert len(await rq.get_categories_with_counts(harness.tg_id)) == 10


async def test_add_expense_flow(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Добавить расход")
    assert "Расход: выберите категорию" in harness.text

    food = await category_id(harness.tg_id, "Еда", "expense")
    await harness.press(f"categ_{food}")
    assert "Категория: Еда" in harness.text
    assert "Введите сумму" in harness.text

    await harness.send("1 250,50")
    assert "Расход: 1 250,50" in harness.text
    assert "Категория: Еда" in harness.text

    assert await rq.count_transactions(harness.tg_id) == 1
    assert await rq.get_stats(harness.tg_id, "all") == (
        Decimal("0.00"),
        Decimal("1250.50"),
    )


async def test_add_income_flow(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Добавить доход")

    salary = await category_id(harness.tg_id, "Зарплата", "income")
    await harness.press(f"categ_{salary}")
    await harness.send("1000")

    assert "Доход: 1 000,00" in harness.text
    assert await rq.get_stats(harness.tg_id, "all") == (
        Decimal("1000.00"),
        Decimal("0.00"),
    )


async def test_amount_validation_keeps_flow_open(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Добавить расход")
    food = await category_id(harness.tg_id, "Еда", "expense")
    await harness.press(f"categ_{food}")

    await harness.send("abc")
    assert "Введите положительное число" in harness.text

    await harness.send("0")
    assert "Введите положительное число" in harness.text

    await harness.send("1000000001")
    assert "Слишком большая сумма" in harness.text

    await harness.send("10,005")
    assert "Расход: 10,01" in harness.text
    assert await rq.count_transactions(harness.tg_id) == 1


async def test_wrong_category_for_selected_type(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Добавить доход")

    food = await category_id(harness.tg_id, "Еда", "expense")
    await harness.press(f"categ_{food}")

    assert harness.callback["alert"] is True
    assert "не найдена" in harness.callback["text"]
    assert await rq.count_transactions(harness.tg_id) == 0


async def test_categories_screen_shows_counts(harness: BotHarness) -> None:
    await harness.send("/start")
    food = await category_id(harness.tg_id, "Еда", "expense")
    await rq.add_transaction(harness.tg_id, food, Decimal("100"), "expense")

    await harness.send("Управление категориями")

    assert "Расходы (6)" in harness.text
    assert "Доходы (4)" in harness.text
    assert "• Еда — 1 операция" in harness.text
    assert "cat_add" in harness.buttons
    assert "cat_defaults" not in harness.buttons


async def test_add_category_rejects_duplicate_case_insensitively(
    harness: BotHarness,
) -> None:
    await harness.send("/start")
    await harness.send("Управление категориями")

    await harness.press("cat_add")
    assert "Введите название" in harness.text

    await harness.send("еда")
    assert "Выберите тип" in harness.text

    # В расходах «Еда» уже есть, регистр не важен.
    await harness.press("type_expense")
    assert harness.callback["alert"] is True
    assert "уже есть категория" in harness.callback["text"]

    # В доходах такого имени ещё нет.
    await harness.press("type_income")
    assert "• еда" in harness.text
    assert harness.callback["text"] == "Категория добавлена"
    assert len(await rq.get_categories_with_counts(harness.tg_id)) == 11


async def test_add_category_validates_name(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Управление категориями")
    await harness.press("cat_add")

    await harness.send("x" * 51)
    assert "Название должно быть" in harness.text
    assert await rq.count_transactions(harness.tg_id) == 0

    await harness.send("Кафе")
    assert "Выберите тип" in harness.text
    await harness.press("type_expense")

    assert "Кафе" in harness.text
    assert await category_id(harness.tg_id, "Кафе", "expense")


async def test_delete_category_with_transactions(harness: BotHarness) -> None:
    await harness.send("/start")
    food = await category_id(harness.tg_id, "Еда", "expense")
    await rq.add_transaction(harness.tg_id, food, Decimal("500"), "expense")

    await harness.send("Управление категориями")
    assert "• Еда — 1 операция" in harness.text

    await harness.press(f"delcat_{food}")
    assert "удалятся операции: 1" in harness.text

    await harness.press(f"delcat_ok_{food}")
    assert "• Еда" not in harness.text
    assert harness.callback["text"] == "Удалено операций: 1"
    assert await rq.get_stats(harness.tg_id, "all") == (
        Decimal("0.00"),
        Decimal("0.00"),
    )

    # Кнопка от удалённой категории больше не работает.
    await harness.press(f"delcat_{food}")
    assert harness.callback["alert"] is True
    assert "уже удалена" in harness.callback["text"]


async def test_restore_default_categories_button(harness: BotHarness) -> None:
    await harness.send("/start")
    food = await category_id(harness.tg_id, "Еда", "expense")
    await rq.delete_category(harness.tg_id, food)

    await harness.send("Управление категориями")
    assert "cat_defaults" in harness.buttons

    await harness.press("cat_defaults")
    assert "• Еда" in harness.text
    assert harness.callback["text"] == "Добавлено категорий: 1"
    assert "cat_defaults" not in harness.buttons

    await harness.press("cat_defaults")
    assert harness.callback["text"] == "Все базовые категории уже есть"


async def test_empty_categories_state(harness: BotHarness) -> None:
    await harness.send("/start")
    for category, _ in await rq.get_categories_with_counts(harness.tg_id):
        await rq.delete_category(harness.tg_id, category.id)

    await harness.send("Управление категориями")
    assert "Категорий пока нет" in harness.text

    await harness.send("Добавить расход")
    assert "У вас пока нет категорий" in harness.text


async def test_close_returns_to_menu(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Управление категориями")
    await harness.press("close")

    assert "Выберите действие в меню" in harness.text
    assert "Добавить расход" in harness.reply_keyboard


async def test_history_pagination_and_deletion(harness: BotHarness) -> None:
    await harness.send("/start")
    food = await category_id(harness.tg_id, "Еда", "expense")
    for amount in range(1, 13):
        await rq.add_transaction(
            harness.tg_id, food, Decimal(str(amount)), "expense"
        )

    await harness.send("История")
    assert "Операции: 12" in harness.text
    assert len(numbered_lines(harness.text)) == 10
    assert "hist_10" in harness.buttons
    assert "Еда · −12,00" in harness.text

    await harness.press("hist_10")
    assert len(numbered_lines(harness.text)) == 2
    assert "hist_0" in harness.buttons
    assert "hist_20" not in harness.buttons

    await harness.press("hist_0")
    assert len(numbered_lines(harness.text)) == 10

    transaction, _ = (await rq.get_transactions(harness.tg_id, 10, 0))[0]
    await harness.press(f"deltx_{transaction.id}_0")
    assert "Удалить операцию?" in harness.text
    assert "−12,00" in harness.text

    await harness.press(f"deltx_ok_{transaction.id}_0")
    assert "Операции: 11" in harness.text
    assert harness.callback["text"] == "Операция удалена"
    assert await rq.count_transactions(harness.tg_id) == 11

    # Повторное нажатие на устаревшую кнопку.
    await harness.press(f"deltx_ok_{transaction.id}_0")
    assert harness.callback["alert"] is True
    assert "уже удалена" in harness.callback["text"]


async def test_history_is_empty_at_start(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("История")

    assert "Операций пока нет" in harness.text
    assert await rq.count_transactions(harness.tg_id) == 0


async def test_stats_breakdown_and_balance(harness: BotHarness) -> None:
    await harness.send("/start")
    food = await category_id(harness.tg_id, "Еда", "expense")
    transport = await category_id(harness.tg_id, "Транспорт", "expense")
    salary = await category_id(harness.tg_id, "Зарплата", "income")

    await rq.add_transaction(harness.tg_id, food, Decimal("300"), "expense")
    await rq.add_transaction(harness.tg_id, transport, Decimal("100"), "expense")
    await rq.add_transaction(harness.tg_id, salary, Decimal("1000"), "income")

    await harness.send("Статистика")
    assert "Выберите период" in harness.text

    await harness.press("period_all")
    assert "Статистика за всё время" in harness.text
    assert "Доходы: 1 000,00" in harness.text
    assert "Расходы: 400,00" in harness.text
    assert "Итог: +600,00" in harness.text
    assert "• Еда — 75% (300,00 ₽)" in harness.text
    assert "• Транспорт — 25% (100,00 ₽)" in harness.text
    assert "Баланс за всё время" not in harness.text

    await harness.send("Статистика")
    await harness.press("period_month")
    assert "Баланс за всё время: +600,00" in harness.text


async def test_stats_empty_period(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Статистика")
    await harness.press("period_today")

    assert "За этот период операций нет" in harness.text


async def test_cancel_shows_stale_callback_alert(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("Добавить расход")
    food = await category_id(harness.tg_id, "Еда", "expense")
    await harness.press(f"categ_{food}")

    await harness.send("/cancel")
    assert "Действие отменено" in harness.text

    await harness.press(f"categ_{food}")
    assert harness.callback["alert"] is True
    assert "устарела" in harness.callback["text"]

    await harness.send("привет")
    assert "Не понял сообщение" in harness.text


async def test_cancel_without_active_dialog(harness: BotHarness) -> None:
    await harness.send("/start")
    await harness.send("/cancel")

    assert "Нечего отменять" in harness.text


async def test_menu_works_during_fsm(harness: BotHarness) -> None:
    """Регрессия P0: меню не должно перехватываться обработчиком состояния."""
    await harness.send("/start")
    await harness.send("Добавить расход")
    food = await category_id(harness.tg_id, "Еда", "expense")
    await harness.press(f"categ_{food}")

    await harness.send("Статистика")
    assert "Выберите период" in harness.text

    await harness.send("История")
    assert "Операций пока нет" in harness.text
