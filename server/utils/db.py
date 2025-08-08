import os


def get_db_path() -> str:
    """Return the SQLite DB path from MCP_DB_PATH or default."""
    return os.getenv("MCP_DB_PATH", "data/mcp.db")
