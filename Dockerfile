# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install -U pip \
    && pip install -r requirements.txt

# Copy app code
COPY server ./server
COPY memory ./memory
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Env defaults
ENV PATH="/opt/venv/bin:$PATH" \
    MCP_TOKEN=change-me

EXPOSE 8080

# Require DATABASE_URL and start server (migrations run via dedicated migrate service)
CMD /bin/sh -c "set -e; if [ -z \"$DATABASE_URL\" ]; then echo 'DATABASE_URL is required' >&2; exit 1; fi; exec uvicorn server.main:app --host 0.0.0.0 --port 8080"
