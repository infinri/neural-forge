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
COPY server/db/schema.sql ./server/db/schema.sql
COPY memory ./memory
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Env defaults
ENV PATH="/opt/venv/bin:$PATH" \
    MCP_TOKEN=change-me \
    MCP_DB_PATH=/data/mcp.db

# Create data dir
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

# If DATABASE_URL is set, attempt Alembic migrations with simple retry; otherwise init SQLite
CMD /bin/sh -c "set -e; \
  if [ -n \"$DATABASE_URL\" ]; then \
    echo 'DATABASE_URL detected; applying Alembic migrations (or stamping if already applied)'; \
    alembic upgrade head || { echo 'Upgrade failed, stamping head as fallback'; alembic stamp head; }; \
  else \
    echo 'No DATABASE_URL; initializing SQLite at '"$MCP_DB_PATH"; \
    python server/db/init_db.py --db $MCP_DB_PATH --schema server/db/schema.sql; \
  fi; \
  exec uvicorn server.main:app --host 0.0.0.0 --port 8080"
