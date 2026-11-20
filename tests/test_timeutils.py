from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import timeutils


def assert_close(actual: datetime, expected: datetime) -> None:
    assert abs(actual - expected) < timedelta(seconds=10)


def test_without_timezone_uses_server_time(monkeypatch) -> None:
    monkeypatch.setattr(timeutils, "TIMEZONE", None)
    assert_close(timeutils.now(), datetime.now())


def test_uses_configured_timezone(monkeypatch) -> None:
    monkeypatch.setattr(timeutils, "TIMEZONE", "Asia/Tokyo")

    expected = datetime.now(ZoneInfo("Asia/Tokyo")).replace(tzinfo=None)
    assert_close(timeutils.now(), expected)


def test_naive_datetime_has_no_tzinfo(monkeypatch) -> None:
    monkeypatch.setattr(timeutils, "TIMEZONE", "Europe/Moscow")
    assert timeutils.now().tzinfo is None


def test_unknown_timezone_falls_back_to_server_time(monkeypatch) -> None:
    monkeypatch.setattr(timeutils, "TIMEZONE", "Mars/Olympus")
    assert_close(timeutils.now(), datetime.now())
