from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")

MAX_AMOUNT = Decimal("1000000000.00")
MAX_CATEGORY_NAME = 50


def parse_amount(raw: str | None) -> Decimal | None:
    """Превращает ввод пользователя в Decimal с точностью до копеек.

    Принимает "1250.50", "1250,50", "1 250,50", "1\u00a0250.5".
    """
    if not raw:
        return None

    cleaned = raw.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None

    try:
        value = Decimal(cleaned)
        if not value.is_finite():
            return None
        value = value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

    return value


def format_money(value: Decimal, signed: bool = False) -> str:
    """Форматирует сумму в виде 1 250,50."""
    amount = Decimal(value).quantize(TWO_PLACES)
    formatted = f"{amount:+,.2f}" if signed else f"{amount:,.2f}"
    return formatted.replace(",", "\u2009").replace(".", ",")
