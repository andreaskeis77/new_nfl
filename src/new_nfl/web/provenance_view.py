"""Read service for the T2.6G Provenance-Drilldown view (ADR-0029).

Exposes two entry points over ``mart.provenance_v1``:

* ``list_provenance(settings, offset=0, limit=50, scope_type=None)`` —
  paginated listing of scope rows. Useful as a landing page for the
  drilldown (``/provenance``) and for scope-type-filtered views like
  ``/provenance/team``.
* ``get_provenance(settings, scope_type, scope_ref)`` — per-scope detail
  lookup, case-insensitive on both ``scope_type`` and ``scope_ref``.

The service never touches ``meta.*`` or ``core.*`` directly — it reads
``mart.provenance_v1`` exclusively (enforced by the AST-lint in
``tests/test_mart.py::READ_MODULES``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_TABLE = "mart.provenance_v1"


@dataclass(frozen=True)
class ProvenanceRecord:
    scope_type: str
    scope_ref: str
    source_file_ids: tuple[str, ...]
    source_adapter_ids: tuple[str, ...]
    first_seen_at: datetime | None
    last_canonicalized_at: datetime | None
    source_row_count: int
    quarantine_case_count: int
    open_quarantine_count: int
    last_reason_code: str | None
    last_severity: str | None
    last_status: str | None
    last_quarantine_at: datetime | None
    provenance_status: str

    @property
    def source_file_count(self) -> int:
        return len(self.source_file_ids)

    @property
    def adapter_count(self) -> int:
        return len(self.source_adapter_ids)

    @property
    def primary_adapter(self) -> str | None:
        if not self.source_adapter_ids:
            return None
        return self.source_adapter_ids[0]

    @property
    def status_label(self) -> str:
        if self.provenance_status == "warn":
            return "Quarantäne offen"
        if self.provenance_status == "unknown":
            return "Keine Provenienz"
        return "OK"

    @property
    def quarantine_label(self) -> str:
        if self.quarantine_case_count == 0:
            return "—"
        if self.open_quarantine_count == 0:
            return f"{self.quarantine_case_count} geschlossen"
        if self.open_quarantine_count == self.quarantine_case_count:
            return f"{self.open_quarantine_count} offen"
        return (
            f"{self.open_quarantine_count} offen / "
            f"{self.quarantine_case_count} total"
        )


@dataclass(frozen=True)
class ProvenanceListPage:
    rows: tuple[ProvenanceRecord, ...]
    offset: int
    limit: int
    total: int
    scope_type_filter: str | None

    @property
    def has_prev(self) -> bool:
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total

    @property
    def prev_offset(self) -> int:
        return max(0, self.offset - self.limit)

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit

    @property
    def page_range_label(self) -> str:
        if self.total == 0:
            return "0"
        start = self.offset + 1
        end = min(self.offset + self.limit, self.total)
        return f"{start}–{end} von {self.total}"


def _connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(settings.db_path))


def _table_exists(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return False
    return True


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if v is not None)
    return ()


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _row_to_record(row: tuple[Any, ...]) -> ProvenanceRecord:
    return ProvenanceRecord(
        scope_type=str(row[0]),
        scope_ref=str(row[1]),
        source_file_ids=_coerce_str_tuple(row[2]),
        source_adapter_ids=_coerce_str_tuple(row[3]),
        first_seen_at=_coerce_datetime(row[4]),
        last_canonicalized_at=_coerce_datetime(row[5]),
        source_row_count=int(row[6] or 0),
        quarantine_case_count=int(row[7] or 0),
        open_quarantine_count=int(row[8] or 0),
        last_reason_code=row[9],
        last_severity=row[10],
        last_status=row[11],
        last_quarantine_at=_coerce_datetime(row[12]),
        provenance_status=str(row[13] or "unknown"),
    )


_SELECT_COLS = """
scope_type,
scope_ref,
source_file_ids,
source_adapter_ids,
first_seen_at,
last_canonicalized_at,
source_row_count,
quarantine_case_count,
open_quarantine_count,
last_reason_code,
last_severity,
last_status,
last_quarantine_at,
provenance_status
"""


def list_provenance(
    settings: Settings,
    *,
    offset: int = 0,
    limit: int = 50,
    scope_type: str | None = None,
) -> ProvenanceListPage:
    con = _connect(settings)
    try:
        if not _table_exists(con, _MART_TABLE):
            return ProvenanceListPage(
                rows=(), offset=0, limit=limit, total=0,
                scope_type_filter=scope_type,
            )
        where_sql = ""
        params: list[Any] = []
        if scope_type is not None:
            where_sql = " WHERE scope_type_lower = LOWER(?)"
            params.append(scope_type)
        total = int(
            con.execute(
                f"SELECT COUNT(*) FROM {_MART_TABLE}{where_sql}", params
            ).fetchone()[0]
        )
        rows = con.execute(
            f"""
            SELECT {_SELECT_COLS}
            FROM {_MART_TABLE}
            {where_sql}
            ORDER BY open_quarantine_count DESC,
                     last_canonicalized_at DESC NULLS LAST,
                     scope_type, scope_ref
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    finally:
        con.close()
    return ProvenanceListPage(
        rows=tuple(_row_to_record(r) for r in rows),
        offset=offset,
        limit=limit,
        total=total,
        scope_type_filter=scope_type,
    )


def get_provenance(
    settings: Settings,
    scope_type: str,
    scope_ref: str,
) -> ProvenanceRecord | None:
    con = _connect(settings)
    try:
        if not _table_exists(con, _MART_TABLE):
            return None
        row = con.execute(
            f"""
            SELECT {_SELECT_COLS}
            FROM {_MART_TABLE}
            WHERE scope_type_lower = LOWER(?)
              AND scope_ref_lower = LOWER(?)
            LIMIT 1
            """,
            [scope_type, scope_ref],
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return _row_to_record(row)


__all__ = [
    "ProvenanceListPage",
    "ProvenanceRecord",
    "get_provenance",
    "list_provenance",
]
