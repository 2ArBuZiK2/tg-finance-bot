"""Единая точка получения текущего времени.

В SQLite даты хранятся без часового пояса, поэтому now() возвращает
naive-datetime с настенными часами выбранного пояса. Если TIMEZONE не
задан, используется время сервера — прежнее поведение.
"""

import logging
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import TIMEZONE

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _load_timezone(name: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Часовой пояс TIMEZONE=%r не найден, использую время сервера", name
        )
        return None


def now() -> datetime:
    """Текущее время в настроенном поясе без tzinfo."""
    timezone = _load_timezone(TIMEZONE) if TIMEZONE else None
    if timezone is None:
        return datetime.now()
    return datetime.now(timezone).replace(tzinfo=None)
