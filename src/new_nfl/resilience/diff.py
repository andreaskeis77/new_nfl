"""Row-level table diff used by the replay drill (T2.7D).

``diff_tables(con_a, con_b, table, key_cols, exclude_cols=...)`` returns
three disjoint row lists that together reconstruct the symmetric
difference between a pre-state snapshot and a post-state rebuild. The
default exclude-list is the non-negotiable floor for replay: timestamp
columns that the core-load stamps on *every* row with
``CURRENT_TIMESTAMP`` would otherwise flip every row to ``changed``.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import duckdb

DEFAULT_EXCLUDE_COLS: tuple[str, ...] = ("_canonicalized_at", "_loaded_at")


@dataclass(frozen=True)
class TableDiff:
    """Symmetric difference between two snapshots of a single table.

    ``only_in_a`` and ``only_in_b`` are whole rows keyed by ``key_cols``
    that exist on exactly one side. ``changed`` contains rows whose key
    exists on both sides but whose non-excluded columns disagree — each
    entry is a ``(row_a, row_b)`` pair so the operator can see both sides.
    """

    table: str
    key_cols: tuple[str, ...]
    exclude_cols: tuple[str, ...]
    only_in_a: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    only_in_b: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    changed: tuple[tuple[dict[str, Any], dict[str, Any]], ...] = field(
        default_factory=tuple
    )

    @property
    def is_empty(self) -> bool:
        return not (self.only_in_a or self.only_in_b or self.changed)

    def summary(self) -> dict[str, int]:
        return {
            "only_in_a": len(self.only_in_a),
            "only_in_b": len(self.only_in_b),
            "changed": len(self.changed),
        }


def _fetch_rows(
    con: duckdb.DuckDBPyConnection,
    table: str,
) -> list[dict[str, Any]]:
    """Fetch every row of ``table`` as a list of dicts.

    TIMESTAMPTZ columns are cast to VARCHAR in-flight so the fetch never
    triggers DuckDB's optional ``pytz`` codepath — pytz is not a project
    dependency, and this module must run on the baseline environment.
    Because the default ``exclude_cols`` already masks the canonical
    timestamp columns, the cast does not change diff semantics for
    non-timestamp data.
    """
    select_list = _build_select_list(con, table)
    result = con.execute(f"SELECT {select_list} FROM {table}")
    cols = [item[0] for item in result.description]
    return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]


def _build_select_list(
    con: duckdb.DuckDBPyConnection, table: str
) -> str:
    """Return a ``SELECT`` column-list with TIMESTAMPTZ columns cast to VARCHAR.

    Falls back to ``*`` if ``information_schema`` cannot resolve the table
    (e.g., in-memory test fixtures without explicit schema rows).
    """
    schema, _, name = table.partition(".")
    if not schema or not name:
        return "*"
    try:
        cols = con.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            [schema, name],
        ).fetchall()
    except duckdb.Error:
        return "*"
    if not cols:
        return "*"
    parts: list[str] = []
    for col_name, data_type in cols:
        if "TIME ZONE" in str(data_type).upper():
            parts.append(f'CAST("{col_name}" AS VARCHAR) AS "{col_name}"')
        else:
            parts.append(f'"{col_name}"')
    return ", ".join(parts)


def _row_key(row: dict[str, Any], key_cols: Sequence[str]) -> tuple[Any, ...]:
    return tuple(row.get(col) for col in key_cols)


def _project(
    row: dict[str, Any], exclude_cols: Iterable[str]
) -> dict[str, Any]:
    excluded = set(exclude_cols)
    return {col: val for col, val in row.items() if col not in excluded}


def diff_tables(
    con_a: duckdb.DuckDBPyConnection,
    con_b: duckdb.DuckDBPyConnection,
    table: str,
    key_cols: Sequence[str],
    exclude_cols: Sequence[str] = DEFAULT_EXCLUDE_COLS,
) -> TableDiff:
    """Compare ``table`` across two DuckDB connections.

    ``key_cols`` must uniquely identify a row in ``table``; ``exclude_cols``
    are ignored for the value-equality test but kept on returned rows so
    the operator can inspect them if something surprising turns up. Rows
    are materialised into memory — the caller is responsible for using
    fixture-sized or already-filtered snapshots in tests.
    """
    if not key_cols:
        raise ValueError("key_cols must be non-empty")
    key_cols_tuple = tuple(key_cols)
    exclude_cols_tuple = tuple(exclude_cols)

    rows_a = _fetch_rows(con_a, table)
    rows_b = _fetch_rows(con_b, table)

    index_a = {_row_key(row, key_cols_tuple): row for row in rows_a}
    index_b = {_row_key(row, key_cols_tuple): row for row in rows_b}

    keys_a = set(index_a)
    keys_b = set(index_b)

    only_a = tuple(index_a[k] for k in sorted(keys_a - keys_b, key=_nullsafe))
    only_b = tuple(index_b[k] for k in sorted(keys_b - keys_a, key=_nullsafe))

    changed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for key in sorted(keys_a & keys_b, key=_nullsafe):
        row_a = index_a[key]
        row_b = index_b[key]
        proj_a = _project(row_a, exclude_cols_tuple)
        proj_b = _project(row_b, exclude_cols_tuple)
        if proj_a != proj_b:
            changed.append((row_a, row_b))

    return TableDiff(
        table=table,
        key_cols=key_cols_tuple,
        exclude_cols=exclude_cols_tuple,
        only_in_a=only_a,
        only_in_b=only_b,
        changed=tuple(changed),
    )


def _nullsafe(key: tuple[Any, ...]) -> tuple[tuple[int, Any], ...]:
    """Sort key that keeps NULLs last and tolerates mixed types."""
    return tuple((0, v) if v is not None else (1, "") for v in key)


__all__ = [
    "DEFAULT_EXCLUDE_COLS",
    "TableDiff",
    "diff_tables",
]
