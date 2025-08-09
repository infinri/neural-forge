import tempfile
from pathlib import Path

import pytest

from server.utils.db import sqlite_fetch_all


@pytest.mark.asyncio
async def test_sqlite_fetch_all_select_one():
    """sqlite_fetch_all should execute a simple SELECT and return rows."""
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        rows = await sqlite_fetch_all("SELECT 1", db_path=db)
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert rows[0][0] == 1
