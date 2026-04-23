"""Tests for ``diff_tables`` (T2.7D).

Isolated from the core-load pipeline so the diff primitive can be audited
without running a full replay drill. Every test builds two throw-away
in-memory DuckDB connections and constructs the two sides row-by-row.
"""
from __future__ import annotations

import duckdb
import pytest

from new_nfl.resilience.diff import DEFAULT_EXCLUDE_COLS, TableDiff, diff_tables


def _new_con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(":memory:")


def _setup_table(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS probe")
    con.execute(
        """
        CREATE OR REPLACE TABLE probe.t (
            id VARCHAR,
            season INTEGER,
            value VARCHAR,
            _canonicalized_at TIMESTAMP,
            _loaded_at TIMESTAMP
        )
        """
    )
    if rows:
        con.executemany(
            "INSERT INTO probe.t VALUES (?, ?, ?, ?, ?)",
            rows,
        )


def test_diff_identical_tables_is_empty() -> None:
    con_a = _new_con()
    con_b = _new_con()
    rows = [
        ("t1", 2024, "alpha", None, None),
        ("t2", 2024, "beta", None, None),
    ]
    _setup_table(con_a, rows)
    _setup_table(con_b, rows)

    result = diff_tables(con_a, con_b, "probe.t", key_cols=["id"])
    assert result.is_empty
    assert result.summary() == {"only_in_a": 0, "only_in_b": 0, "changed": 0}


def test_diff_only_in_a_surfaces_missing_row_on_the_right() -> None:
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(
        con_a,
        [
            ("t1", 2024, "alpha", None, None),
            ("t2", 2024, "beta", None, None),
        ],
    )
    _setup_table(con_b, [("t1", 2024, "alpha", None, None)])

    result = diff_tables(con_a, con_b, "probe.t", key_cols=["id"])
    assert result.summary() == {"only_in_a": 1, "only_in_b": 0, "changed": 0}
    assert result.only_in_a[0]["id"] == "t2"


def test_diff_only_in_b_surfaces_missing_row_on_the_left() -> None:
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(con_a, [("t1", 2024, "alpha", None, None)])
    _setup_table(
        con_b,
        [
            ("t1", 2024, "alpha", None, None),
            ("t2", 2024, "beta", None, None),
        ],
    )

    result = diff_tables(con_a, con_b, "probe.t", key_cols=["id"])
    assert result.summary() == {"only_in_a": 0, "only_in_b": 1, "changed": 0}
    assert result.only_in_b[0]["id"] == "t2"


def test_diff_changed_row_on_non_excluded_column() -> None:
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(con_a, [("t1", 2024, "alpha", None, None)])
    _setup_table(con_b, [("t1", 2024, "BRAVO", None, None)])

    result = diff_tables(con_a, con_b, "probe.t", key_cols=["id"])
    assert result.summary() == {"only_in_a": 0, "only_in_b": 0, "changed": 1}
    row_a, row_b = result.changed[0]
    assert row_a["value"] == "alpha"
    assert row_b["value"] == "BRAVO"


def test_diff_ignores_excluded_timestamp_columns_by_default() -> None:
    """``_canonicalized_at`` / ``_loaded_at`` must not flip rows to 'changed'.

    This is the non-negotiable contract that lets the replay drill
    declare a clean re-run successful.
    """
    import datetime as _dt

    ts1 = _dt.datetime(2026, 4, 23, 10, 0, 0)
    ts2 = _dt.datetime(2026, 4, 23, 11, 0, 0)
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(con_a, [("t1", 2024, "alpha", ts1, ts1)])
    _setup_table(con_b, [("t1", 2024, "alpha", ts2, ts2)])

    result = diff_tables(con_a, con_b, "probe.t", key_cols=["id"])
    assert result.is_empty
    assert result.exclude_cols == DEFAULT_EXCLUDE_COLS


def test_diff_honours_custom_exclude_cols() -> None:
    """Explicit ``exclude_cols=[]`` exposes the timestamp delta."""
    import datetime as _dt

    ts1 = _dt.datetime(2026, 4, 23, 10, 0, 0)
    ts2 = _dt.datetime(2026, 4, 23, 11, 0, 0)
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(con_a, [("t1", 2024, "alpha", ts1, ts1)])
    _setup_table(con_b, [("t1", 2024, "alpha", ts2, ts2)])

    result = diff_tables(con_a, con_b, "probe.t", key_cols=["id"], exclude_cols=[])
    assert result.summary()["changed"] == 1


def test_diff_composite_key_partitions_rows() -> None:
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(
        con_a,
        [
            ("t1", 2024, "alpha", None, None),
            ("t1", 2025, "beta", None, None),
        ],
    )
    _setup_table(
        con_b,
        [
            ("t1", 2024, "alpha", None, None),
            ("t1", 2025, "GAMMA", None, None),
        ],
    )

    result = diff_tables(
        con_a, con_b, "probe.t", key_cols=["id", "season"]
    )
    assert result.summary() == {"only_in_a": 0, "only_in_b": 0, "changed": 1}
    row_a, row_b = result.changed[0]
    assert row_a["season"] == 2025
    assert row_b["value"] == "GAMMA"


def test_diff_empty_key_cols_raises() -> None:
    con_a = _new_con()
    con_b = _new_con()
    _setup_table(con_a, [])
    _setup_table(con_b, [])

    with pytest.raises(ValueError, match="key_cols must be non-empty"):
        diff_tables(con_a, con_b, "probe.t", key_cols=[])


def test_table_diff_is_frozen_dataclass() -> None:
    diff = TableDiff(table="probe.t", key_cols=("id",), exclude_cols=())
    with pytest.raises((AttributeError, Exception)):
        diff.table = "x"  # type: ignore[misc]
