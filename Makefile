.PHONY: setup install run dev test fmt lint clean db-upgrade db-downgrade db-current

PY?=python3
VENv=.venv
ACTIVATE=$(VENv)/bin/activate
DB_PATH?=data/mcp.db

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

db-init:
	mkdir -p $(dir $(DB_PATH))
	. $(ACTIVATE) && $(PY) server/db/init_db.py --db $(DB_PATH) --schema server/db/schema.sql

test:
	. $(ACTIVATE) && MCP_TOKEN=dev MCP_DB_PATH=$(DB_PATH) pytest -q

fmt:
	. $(ACTIVATE) && ruff check --fix .

lint:
	. $(ACTIVATE) && ruff check . && mypy --ignore-missing-imports server

clean:
	rm -rf $(VENv) __pycache__ .pytest_cache

# --- Alembic (Postgres) ---
db-upgrade:
	. $(ACTIVATE) && DATABASE_URL=$${DATABASE_URL} alembic upgrade head

db-downgrade:
	. $(ACTIVATE) && DATABASE_URL=$${DATABASE_URL} alembic downgrade -1

db-current:
	. $(ACTIVATE) && DATABASE_URL=$${DATABASE_URL} alembic current -v
