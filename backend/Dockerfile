# syntax=docker/dockerfile:1
FROM python:3.12-slim AS backend

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Python dependencies only. psycopg[binary] ships libpq wheels, so no system
# packages are required to talk to PostgreSQL.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Apply pending migrations, then serve the API on port 8000.
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
