FROM python:3.12-slim AS base

WORKDIR /usr/src/app

# System deps for psycopg2 / asyncpg builds, plus postgresql-client for
# pg_dump (app/routers/backups.py — the Admin Panel's Backups module)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser \
    && mkdir -p uploads logs \
    && chown -R appuser:appuser /usr/src/app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4"]
