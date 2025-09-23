.PHONY: setup install run dev test fmt lint clean db-upgrade db-downgrade db-current

PY?=python3
VENv=.venv
ACTIVATE=$(VENv)/bin/activate

setup:
	$(PY) -m venv $(VENv)
	. $(ACTIVATE) && pip install -U pip && pip install -r requirements.txt

install:
	. $(ACTIVATE) || true; \
	pip install -U pip && pip install -r requirements.txt

run:
	. $(ACTIVATE) && uvicorn server.main:app --host 127.0.0.1 --port 8080

dev:
	. $(ACTIVATE) && uvicorn server.main:app --reload --host 127.0.0.1 --port 8080

test:
. $(ACTIVATE) && MCP_TOKEN=test-token pytest -q

fmt:
	. $(ACTIVATE) && ruff check --fix .

lint:
	. $(ACTIVATE) && ruff check . && mypy --ignore-missing-imports server

clean:
	rm -rf $(VENv) __pycache__ .pytest_cache

# --- Alembic (Postgres) ---
# Host migrations using sync driver (psycopg). Requires ALEMBIC_DATABASE_URL.
db-upgrade:
	. $(ACTIVATE) && ALEMBIC_DATABASE_URL=$${ALEMBIC_DATABASE_URL} alembic upgrade head

db-downgrade:
	. $(ACTIVATE) && ALEMBIC_DATABASE_URL=$${ALEMBIC_DATABASE_URL} alembic downgrade -1

db-current:
	. $(ACTIVATE) && ALEMBIC_DATABASE_URL=$${ALEMBIC_DATABASE_URL} alembic current -v

# Containerized migrations (recommended): runs inside Compose network.
db-upgrade-docker:
	docker compose run --rm migrate
