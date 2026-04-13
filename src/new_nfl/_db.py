"""Shared DuckDB helpers for NEW NFL submodules.

Introduced in T2.3B to prevent further `_connect`/`_row_to_dict`/`_new_id`
duplication across `jobs/`, `quarantine/`, `ontology/` etc. The existing
helpers inside `metadata.py` keep their private shape for historical
reasons; new modules should import from here.
"""
from __future__ import annotations

import uuid
from typing import Any

import duckdb

from new_nfl.settings import Settings


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection against the configured database path."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.db_path))


def row_to_dict(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute a SELECT and return a list of dict rows keyed by column name."""
    result = con.execute(sql, params or [])
    cols = [item[0] for item in result.description]
    return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]


def new_id() -> str:
    """Return a fresh UUID4 string for use as a primary key."""
    return str(uuid.uuid4())
