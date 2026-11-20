import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Необязательный часовой пояс в формате IANA (например, Europe/Moscow).
# Влияет на границы «сегодня» и «этот месяц» и на даты новых операций.
TIMEZONE = (os.getenv("TIMEZONE") or "").strip() or None

# Путь к БД не зависит от текущей рабочей директории:
# запуск из любой папки использует один и тот же файл.
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"sqlite+aiosqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}"
)
