import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Путь к БД не зависит от текущей рабочей директории:
# запуск из любой папки использует один и тот же файл.
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"sqlite+aiosqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}"
)
