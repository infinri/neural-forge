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
    ap = argparse.ArgumentParser(description="Initialize SQLite DB for MCP server")
    ap.add_argument("--db", required=True, help="Path to SQLite DB file, e.g. data/mcp.db")
    ap.add_argument("--schema", required=True, help="Path to schema.sql")
    args = ap.parse_args()

    db_path = Path(args.db)
    schema_path = Path(args.schema)

    if not schema_path.exists():
        raise SystemExit(f"Schema file not found: {schema_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        apply_schema(conn, schema_path)
        print(f"Initialized DB at {db_path} using {schema_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
