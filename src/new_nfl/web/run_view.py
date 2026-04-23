"""Read service for the T2.6H Run-Evidence-Browser view (ADR-0029).

Exposes two entry points over ``mart.run_overview_v1`` /
``mart.run_event_v1`` / ``mart.run_artifact_v1``:

* ``list_runs(settings, offset=0, limit=50, status=None)`` — paginated
  listing of runs with optional status filter. Drives ``/runs``.
* ``get_run_detail(settings, job_run_id)`` — per-run detail bundle
  (meta + event stream + artifact stream), case-insensitive on the
  run id. Drives ``/runs/<job_run_id>``.

The service reads only from ``mart.*`` (enforced by the AST-lint in
``tests/test_mart.py::READ_MODULES``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_OVERVIEW = "mart.run_overview_v1"
_MART_EVENT = "mart.run_event_v1"
_MART_ARTIFACT = "mart.run_artifact_v1"


@dataclass(frozen=True)
class RunSummary:
    job_run_id: str
    job_id: str | None
    job_key: str | None
    job_type: str | None
    run_status: str
    attempt_number: int
    worker_id: str | None
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    event_count: int
    error_event_count: int
    warn_event_count: int
    last_event_recorded_at: datetime | None
    artifact_count: int

    @property
    def status_label(self) -> str:
        mapping = {
            "success": "OK",
            "failed": "Fehlgeschlagen",
            "running": "Läuft",
            "pending": "Wartend",
            "retrying": "Wiederholung",
            "quarantined": "Quarantäne",
        }
        return mapping.get(self.run_status, self.run_status or "—")

    @property
    def duration_label(self) -> str:
        if self.duration_seconds is None:
            return "—"
        seconds = int(self.duration_seconds)
        if seconds < 1:
            return "<1s"
        if seconds < 60:
            return f"{seconds}s"
        minutes, rest = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {rest}s"
        hours, rest_min = divmod(minutes, 60)
        return f"{hours}h {rest_min}m"

    @property
    def job_label(self) -> str:
        return self.job_key or self.job_id or "—"

    @property
    def attempt_label(self) -> str:
        return str(self.attempt_number)

    @property
    def evidence_label(self) -> str:
        parts: list[str] = []
        parts.append(f"{self.event_count} Events")
        if self.error_event_count > 0:
            parts.append(f"{self.error_event_count} err")
        if self.warn_event_count > 0:
            parts.append(f"{self.warn_event_count} warn")
        parts.append(f"{self.artifact_count} Artefakte")
        return " · ".join(parts)


@dataclass(frozen=True)
class RunEventRow:
    run_event_id: str
    job_run_id: str
    event_kind: str
    severity: str | None
    message: str | None
    detail_json: str | None
    recorded_at: datetime | None

    @property
    def severity_label(self) -> str:
        if not self.severity:
            return "—"
        return self.severity


@dataclass(frozen=True)
class RunArtifactRow:
    run_artifact_id: str
    job_run_id: str
    artifact_kind: str
    ref_id: str | None
    ref_path: str | None
    detail_json: str | None
    recorded_at: datetime | None

    @property
    def ref_label(self) -> str:
        if self.ref_path:
            return self.ref_path
        if self.ref_id:
            return self.ref_id
        return "—"


@dataclass(frozen=True)
class RunDetail:
    summary: RunSummary
    events: tuple[RunEventRow, ...]
    artifacts: tuple[RunArtifactRow, ...]


@dataclass(frozen=True)
class RunListPage:
    rows: tuple[RunSummary, ...]
    offset: int
    limit: int
    total: int
    status_filter: str | None

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


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_SUMMARY_COLS = """
job_run_id,
job_id,
job_key,
job_type,
run_status,
attempt_number,
worker_id,
message,
started_at,
finished_at,
duration_seconds,
event_count,
error_event_count,
warn_event_count,
last_event_recorded_at,
artifact_count
"""


def _row_to_summary(row: tuple[Any, ...]) -> RunSummary:
    return RunSummary(
        job_run_id=str(row[0]),
        job_id=row[1],
        job_key=row[2],
        job_type=row[3],
        run_status=str(row[4] or ""),
        attempt_number=int(row[5] or 1),
        worker_id=row[6],
        message=row[7],
        started_at=_coerce_datetime(row[8]),
        finished_at=_coerce_datetime(row[9]),
        duration_seconds=_coerce_float(row[10]),
        event_count=int(row[11] or 0),
        error_event_count=int(row[12] or 0),
        warn_event_count=int(row[13] or 0),
        last_event_recorded_at=_coerce_datetime(row[14]),
        artifact_count=int(row[15] or 0),
    )


def list_runs(
    settings: Settings,
    *,
    offset: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> RunListPage:
    con = _connect(settings)
    try:
        if not _table_exists(con, _MART_OVERVIEW):
            return RunListPage(
                rows=(), offset=0, limit=limit, total=0, status_filter=status
            )
        where_sql = ""
        params: list[Any] = []
        if status is not None:
            where_sql = " WHERE run_status_lower = LOWER(?)"
            params.append(status)
        total = int(
            con.execute(
                f"SELECT COUNT(*) FROM {_MART_OVERVIEW}{where_sql}", params
            ).fetchone()[0]
        )
        rows = con.execute(
            f"""
            SELECT {_SUMMARY_COLS}
            FROM {_MART_OVERVIEW}
            {where_sql}
            ORDER BY started_at DESC NULLS LAST, job_run_id
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    finally:
        con.close()
    return RunListPage(
        rows=tuple(_row_to_summary(r) for r in rows),
        offset=offset,
        limit=limit,
        total=total,
        status_filter=status,
    )


def get_run_detail(
    settings: Settings,
    job_run_id: str,
) -> RunDetail | None:
    con = _connect(settings)
    try:
        if not _table_exists(con, _MART_OVERVIEW):
            return None
        summary_row = con.execute(
            f"""
            SELECT {_SUMMARY_COLS}
            FROM {_MART_OVERVIEW}
            WHERE job_run_id_lower = LOWER(?)
            LIMIT 1
            """,
            [job_run_id],
        ).fetchone()
        if summary_row is None:
            return None
        summary = _row_to_summary(summary_row)
        events: tuple[RunEventRow, ...] = ()
        if _table_exists(con, _MART_EVENT):
            event_rows = con.execute(
                f"""
                SELECT run_event_id, job_run_id, event_kind, severity,
                       message, detail_json, recorded_at
                FROM {_MART_EVENT}
                WHERE job_run_id_lower = LOWER(?)
                ORDER BY recorded_at NULLS LAST, run_event_id
                """,
                [job_run_id],
            ).fetchall()
            events = tuple(
                RunEventRow(
                    run_event_id=str(r[0]),
                    job_run_id=str(r[1]),
                    event_kind=str(r[2] or ""),
                    severity=r[3],
                    message=r[4],
                    detail_json=r[5],
                    recorded_at=_coerce_datetime(r[6]),
                )
                for r in event_rows
            )
        artifacts: tuple[RunArtifactRow, ...] = ()
        if _table_exists(con, _MART_ARTIFACT):
            artifact_rows = con.execute(
                f"""
                SELECT run_artifact_id, job_run_id, artifact_kind, ref_id,
                       ref_path, detail_json, recorded_at
                FROM {_MART_ARTIFACT}
                WHERE job_run_id_lower = LOWER(?)
                ORDER BY recorded_at NULLS LAST, run_artifact_id
                """,
                [job_run_id],
            ).fetchall()
            artifacts = tuple(
                RunArtifactRow(
                    run_artifact_id=str(r[0]),
                    job_run_id=str(r[1]),
                    artifact_kind=str(r[2] or ""),
                    ref_id=r[3],
                    ref_path=r[4],
                    detail_json=r[5],
                    recorded_at=_coerce_datetime(r[6]),
                )
                for r in artifact_rows
            )
    finally:
        con.close()
    return RunDetail(summary=summary, events=events, artifacts=artifacts)


__all__ = [
    "RunArtifactRow",
    "RunDetail",
    "RunEventRow",
    "RunListPage",
    "RunSummary",
    "get_run_detail",
    "list_runs",
]
