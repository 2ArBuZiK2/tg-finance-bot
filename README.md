# 💰 Telegram-бот для учёта личных финансов

[![CI](https://github.com/2ArBuZiK2/tg-finance-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/2ArBuZiK2/tg-finance-bot/actions/workflows/ci.yml)

Телеграм-бот для ведения учёта доходов и расходов с гибкой системой категорий и статистикой за периоды.

## ✨ Возможности

- 📂 **Свои категории** — базовые категории создаются при первом запуске; список с количеством операций, добавление и удаление с подтверждением.
- 💸 **Добавление расходов и доходов** — пошаговый ввод через FSM: выбор категории → ввод суммы.
- ✅ **Валидация суммы** — принимаются положительные суммы с копейками (`1250,50`), тип категории проверяется.
- 📊 **Статистика** — доходы, расходы и итог за сегодня / 7 дней / месяц / всё время, разбивка по категориям с процентами и баланс за всё время.
- 🧾 **История операций** — по 10 операций на страницу, удаление с подтверждением.
- 🕓 **Часовой пояс** — границы дня и месяца считаются в настроенной зоне (`TIMEZONE`), а не по времени сервера.
- ↩️ **Отмена** — команда `/cancel` и кнопка «Отмена» прерывают любой сценарий.
- 🔐 **Изоляция данных** — каждый пользователь видит только свои категории и транзакции.
- 🎛 **Удобное меню** — reply- и inline-клавиатуры, интуитивная навигация.

## 🛠 Стек

- **Python 3.11+** (проверено на 3.13)
- **aiogram 3** — асинхронный фреймворк для Telegram-ботов
- **SQLAlchemy 2.0** — ORM, async-режим
- **SQLite** (aiosqlite) — база данных
- **python-dotenv** — конфигурация через `.env`

## 📁 Структура проекта

```
tg-finance-bot/
├── main.py
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .github/
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── config.py
│   ├── handlers.py
│   ├── keyboards.py
│   ├── states.py
│   ├── utils.py
│   └── database/
│       ├── models.py
│       └── requests.py
└── tests/
    ├── conftest.py
    ├── test_dialogs.py
    ├── test_requests.py
    ├── test_utils.py
    └── support/
        └── harness.py
```

## 🚀 Установка и запуск

1. Клонировать репозиторий:
   ```bash
   git clone <URL_репозитория>
   cd tg-finance-bot
   ```

2. Создать виртуальное окружение и активировать его:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # macOS/Linux
   ```

3. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

4. Скопировать `.env.example` в `.env` и добавить токен:
   ```bash
   cp .env.example .env        # macOS/Linux
   copy .env.example .env      # Windows
   ```
   ```
   BOT_TOKEN=ваш_токен_от_BotFather
   ```

5. Запустить бота:
   ```bash
   python main.py
   ```

## 🧪 Тесты и линтер

Установить dev-зависимости:

```bash
pip install -r requirements-dev.txt
```

Запустить проверки:

```bash
pytest -q
ruff check .
```

Тесты работают с отдельной временной базой SQLite и не трогают `db.sqlite3`. Интеграционные сценарии прогоняют настоящие хендлеры и FSM через поддельную сессию Telegram API: добавление операций, категории, историю с пагинацией, статистику, отмену и устаревшие кнопки. Покрытие измеряется через `pytest-cov`, CI падает при падении ниже 80%.

## 🕓 Часовой пояс

По умолчанию «сегодня» и «этот месяц» считаются по времени сервера, а на VPS это обычно UTC. Чтобы границы дня совпадали с вашим поясом, добавьте в `.env`:

```
TIMEZONE=Europe/Moscow
```

Подойдёт любое имя зоны IANA. Пакет `tzdata` уже в зависимостях, поэтому зоны работают и на Windows, и в slim-образе Docker. Если пояс не задан или указан неверно, бот использует время сервера и пишет предупреждение в лог.

## ⚙️ CI

GitHub Actions запускает `ruff` и `pytest` на Python 3.11 и 3.13 при каждом push в `main` и в pull request. Отдельная job собирает Docker-образ, чтобы Dockerfile не сломался незаметно.

## 🐳 Docker

```bash
docker build -t tg-finance-bot .
docker run -d --name tg-finance-bot \
  --env-file .env \
  -v tg-finance-data:/data \
  --restart unless-stopped \
  tg-finance-bot
```

База хранится в томе `tg-finance-data` (путь `/data/db.sqlite3` задан через `DATABASE_URL`). Токен передаётся через `--env-file .env` и в образ не копируется. При необходимости добавьте в `.env` строку `TIMEZONE=Europe/Moscow` — контейнер подхватит её вместе с остальными переменными.

## 📄 Лицензия

Проект распространяется под лицензией MIT — подробности в [LICENSE](LICENSE).
