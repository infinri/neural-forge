# Neural Forge MCP Server (Python)

A FastAPI-based MCP Memory/Planning server aligned with `windsurf-mcp-memory-blueprint-v1.3-neural-forge.md`.

## Quickstart (Postgres-first)

1. Create venv and install deps
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

2. Bootstrap stack (Docker Compose + migrations)
```bash
# interactive: writes .env, starts compose, runs Alembic, validates
scripts/bootstrap.sh
# Server: http://127.0.0.1:8081
# Prometheus: http://127.0.0.1:9090
# Grafana:    http://127.0.0.1:3000 (anonymous)
```

3. Manual migration flow (optional)
```bash
# ensure Postgres is up (docker compose up -d)
export DATABASE_URL='postgresql+asyncpg://forge:forge@postgres:5432/neural_forge'
make db-upgrade   # alembic upgrade head
make db-current   # show current migration
```

4. Sanity checks
```bash
curl http://127.0.0.1:8081/get_capabilities -H "Authorization: Bearer ${MCP_TOKEN:-dev}"
curl http://127.0.0.1:8081/sse?token=${MCP_TOKEN:-dev}
```

## Project Layout
- `server/main.py`: FastAPI app, tool routing, SSE
- `server/tools/*.py`: MCP tool handlers (stubs matching v1.3 schemas)
- `server/db/`: schema and models
- `.windsurf/`: MCP config and workflows
- `contracts/`: wire/contract docs
- `tasks/`: example task bootstrap

## Configuration

- Env vars:
  - `MCP_TOKEN`: bearer token required for all endpoints (default: `dev`).
  - `DATABASE_URL`: async SQLAlchemy Postgres URL (e.g., `postgresql+asyncpg://forge:forge@postgres:5432/neural_forge`).
  - `MCP_DB_PATH`: SQLite fallback for tests (default: `data/mcp.db`).
- Windsurf MCP client config: see `.windsurf/mcp_config.json` which points SSE to `http://127.0.0.1:8081/sse?token=${MCP_TOKEN}`.

## Metrics & Logging

- Metrics: Prometheus at `/metrics` (uses `prometheus-client`).
  - Counters: `mcp_requests_total{endpoint}`, `mcp_errors_total{endpoint,code}`.
  - Histogram: `mcp_request_duration_seconds{endpoint}`.
- Structured logging: JSON logs emitted from `server/main.py` using `server/utils/logger.py`.
  - Events: `tool_complete`, `tool_http_error`, `tool_exception`.
  - Fields: `endpoint`, `requestId`, `elapsedMs`, `status` or `status_code`, `error`.

## Utilities

- Time: `server/utils/time.py` provides `utc_now_iso_z()` for timezone-aware UTC ISO8601.
- DB: `server/utils/db.py` centralizes DB path via `get_db_path()`.

## CI

- GitHub Actions workflow at `.github/workflows/ci.yml` runs pytest with Python 3.12.
  - Uses `MCP_TOKEN=dev` and `MCP_DB_PATH=data/mcp.ci.db`.

## Docker

- Build and run the MCP server container:

```bash
docker build -t neural-forge-mcp:local .
docker run --rm -p 8081:8080 -e MCP_TOKEN=dev -v $(pwd)/data:/data neural-forge-mcp:local
```

- Full stack with Prometheus + Grafana:

```bash
docker compose up -d
# Server: http://127.0.0.1:8081
# Prometheus: http://127.0.0.1:9090
# Grafana:    http://127.0.0.1:3000 (anonymous)
```

## Database Migrations (Alembic)

- Targets in `Makefile`:
  - `make db-upgrade` → `alembic upgrade head`
  - `make db-downgrade` → `alembic downgrade -1`
  - `make db-current` → show current migration

Initial migration reflects `server/db/pg_schema.sql`.

## Next Steps
- Add Grafana dashboard for the Prometheus metrics (import histogram/counters and latencies by endpoint).
- Document local Prometheus/Grafana docker-compose for observability.
- Extend governance endpoints (`get_governance_policies`, `get_active_tokens`, `get_rules`) per blueprint.
