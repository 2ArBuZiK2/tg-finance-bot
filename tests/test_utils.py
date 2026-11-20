from decimal import Decimal

import pytest

from app.utils import MAX_AMOUNT, format_money, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1250", Decimal("1250.00")),
        ("1250.50", Decimal("1250.50")),
        ("1250,50", Decimal("1250.50")),
        ("1 250,50", Decimal("1250.50")),
        ("1\u00a0250.5", Decimal("1250.50")),
        ("  10,999  ", Decimal("11.00")),
        ("0.005", Decimal("0.01")),
    ],
)
def test_parse_amount_accepts_user_formats(raw: str, expected: Decimal) -> None:
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "abc", "1,2,3", "1.2.3", "nan", "inf", "1e"])
def test_parse_amount_rejects_garbage(raw: str | None) -> None:
    assert parse_amount(raw) is None


def test_parse_amount_keeps_negative_sign_for_callers_to_reject() -> None:
    # Отрицательные суммы отсекают хендлеры и requests.add_transaction.
    assert parse_amount("-5") == Decimal("-5.00")


def test_format_money() -> None:
    assert format_money(Decimal("1250.5")) == "1\u2009250,50"
    assert format_money(Decimal("0")) == "0,00"
    assert format_money(Decimal("1250.5"), signed=True) == "+1\u2009250,50"
    assert format_money(Decimal("-1250.5"), signed=True) == "-1\u2009250,50"


def test_max_amount_is_a_decimal() -> None:
    assert MAX_AMOUNT == Decimal("1000000000.00")
