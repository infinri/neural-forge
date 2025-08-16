#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    # executescript allows multiple statements incl. PRAGMA & CREATE
    conn.executescript(sql)
    conn.commit()


def main() -> None:
    raise SystemExit(
        "Deprecated: SQLite initialization has been removed. "
        "Neural Forge is PostgreSQL-only. Run Alembic migrations instead:\n"
        "  DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db alembic upgrade head\n"
        "See docs/MCP_SERVER_GUIDE.md for details."
    )


if __name__ == "__main__":
    main()
