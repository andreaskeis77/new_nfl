"""Settings-Level-Cache für ``DESCRIBE``-Calls auf ``core.*`` (T2.7E-2).

Motivation: Mart-Rebuilds rufen derzeit bei jedem Durchlauf
``DESCRIBE core.<table>`` auf, um die vorhandenen Spalten zu erheben und
die Projektion gegen fehlende optionale Spalten zu härten (``_opt``-Pattern
in :mod:`new_nfl.mart.player_overview` u. a.). Pro Rebuild sind das 1–2
zusätzliche Abfragen; über alle Marts summiert sich das, sobald UI-Rebuilds
oder Health-Probes die Projektionen hoch-frequent antriggern.

Der Cache hat **drei** Eigenschaften:

1. **TTL-basiert** — ``settings.schema_cache_ttl_seconds`` (Default 300s).
   Nach Ablauf wird der Eintrag verworfen und die nächste Anfrage
   DESCRIBEt erneut.
2. **Pro-Settings-Instance** — Cache-Key enthält ``id(settings)``, sodass
   zwei Tests (mit jeweils eigener Temp-DB und eigenem ``Settings``-Objekt)
   keinen Cross-Talk haben. Single-Process, **nicht** Thread-safe — reicht
   für den Single-Operator-Use-Case.
3. **Connection-aware** — ``describe(settings, table_ref, *, con=...)``
   konsumiert optional eine bestehende Connection. Mart-Rebuilds haben
   ihre eigene Write-Connection offen und vermeiden so eine zweite auf
   dieselbe DuckDB-Datei.

Bei Fehlern im ``DESCRIBE`` (``duckdb.Error``) cachet die Funktion **nicht**
— eine fehlende Tabelle soll beim nächsten Aufruf erneut versuchen, weil
der Operator womöglich zwischen den Calls ``core-load`` fährt.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import duckdb

from new_nfl.settings import Settings

DEFAULT_TTL_SECONDS = 300

# Module-level cache: ``(id(settings), table_ref_normalised)`` → ``_Entry``.
# ``id(settings)`` isoliert Test-Fixtures, die pro Test eine eigene
# ``Settings``-Instance bauen. Beim Garbage-Collect der Settings wird der
# Eintrag nicht proaktiv entfernt — ``invalidate_for`` / ``clear_cache``
# sind die expliziten Exits; über den normalen Programmlauf ist das ein
# bounded, kleiner Footprint (< 20 Tabellen × < 10 Settings gleichzeitig).
_CACHE: dict[tuple[int, str], _Entry] = {}


@dataclass(frozen=True)
class _Entry:
    expires_at: float
    rows: tuple[tuple[Any, ...], ...]


def _ttl_seconds(settings: Settings) -> int:
    raw = getattr(settings, "schema_cache_ttl_seconds", None)
    if raw is None:
        return DEFAULT_TTL_SECONDS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS
    return max(0, value)


def _normalise(table_ref: str) -> str:
    return table_ref.strip().lower()


def describe(
    settings: Settings,
    table_ref: str,
    *,
    con: duckdb.DuckDBPyConnection | None = None,
) -> list[tuple[Any, ...]]:
    """Return ``DESCRIBE <table_ref>`` rows, cached per Settings-Instance.

    ``rows`` are the raw ``fetchall()`` tuples — callers that only want
    column names should project ``row[0]`` themselves (same contract as
    the inline ``con.execute('DESCRIBE …').fetchall()`` they replace).

    Raises :class:`duckdb.Error` (typically ``CatalogException``) if the
    table does not exist; the error is **not** cached, so the next call
    will re-check.
    """
    ttl = _ttl_seconds(settings)
    key = (id(settings), _normalise(table_ref))
    now = time.monotonic()

    entry = _CACHE.get(key)
    if entry is not None and now < entry.expires_at:
        return [tuple(row) for row in entry.rows]

    owns_connection = con is None
    if owns_connection:
        con = duckdb.connect(str(settings.db_path))
    try:
        fetched = con.execute(f"DESCRIBE {table_ref}").fetchall()
    finally:
        if owns_connection and con is not None:
            con.close()

    frozen_rows = tuple(tuple(row) for row in fetched)
    if ttl > 0:
        _CACHE[key] = _Entry(expires_at=now + ttl, rows=frozen_rows)
    return [tuple(row) for row in frozen_rows]


def column_names(
    settings: Settings,
    table_ref: str,
    *,
    con: duckdb.DuckDBPyConnection | None = None,
) -> set[str]:
    """Helper: lowercase set of column names behind ``DESCRIBE <table_ref>``."""
    rows = describe(settings, table_ref, con=con)
    return {str(row[0]).strip().lower() for row in rows if row}


def invalidate_for(settings: Settings, table_ref: str | None = None) -> None:
    """Drop cached entries for ``settings`` — optionally scoped to one table."""
    sid = id(settings)
    if table_ref is None:
        stale_keys = [key for key in _CACHE if key[0] == sid]
    else:
        stale_keys = [(sid, _normalise(table_ref))]
    for key in stale_keys:
        _CACHE.pop(key, None)


def clear_cache() -> None:
    """Drop every cached entry. Exists for tests that need a clean slate."""
    _CACHE.clear()


def cache_size() -> int:
    """Return the number of cached entries. Test/introspection helper."""
    return len(_CACHE)


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "cache_size",
    "clear_cache",
    "column_names",
    "describe",
    "invalidate_for",
]
