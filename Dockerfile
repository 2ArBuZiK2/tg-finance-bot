FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite+aiosqlite:////data/db.sqlite3

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app ./app

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /data \
    && chown bot:bot /data

USER bot

VOLUME ["/data"]

CMD ["python", "main.py"]
