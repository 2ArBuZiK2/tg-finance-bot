"""Общая настройка тестов.

Переменные окружения выставляются до импорта app.*: config читает их при
загрузке модуля. Тестовая база — отдельный временный файл, реальный
db.sqlite3 тесты не трогают.
"""

import itertools
import os
import tempfile
from pathlib import Path

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

TEST_DB = Path(tempfile.gettempdir()) / f"tg_finance_tests_{os.getpid()}.sqlite3"
TEST_DB.unlink(missing_ok=True)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["BOT_TOKEN"] = "42:TEST"
# Тесты не должны зависеть от часового пояса машины разработчика.
os.environ.pop("TIMEZONE", None)

from app.database.models import Base, engine  # noqa: E402
from app.handlers import router  # noqa: E402
from tests.support.harness import BotHarness  # noqa: E402


@pytest.fixture(autouse=True)
async def clean_database():
    """Каждый тест начинается с пустой схемы."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True, scope="session")
def _remove_test_db():
    yield
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def dispatcher() -> Dispatcher:
    """Один Router можно подключить только к одному Dispatcher."""
    result = Dispatcher(storage=MemoryStorage())
    result.include_router(router)
    return result


_harness_ids = itertools.count(900_000_001)


@pytest.fixture
async def harness(dispatcher: Dispatcher):
    bot_harness = BotHarness(dispatcher, next(_harness_ids))
    try:
        yield bot_harness
    finally:
        await bot_harness.close()
