"""Health-response builder for the ``new-nfl health-probe`` CLI (T2.7A).

Produces the canonical JSON envelope

.. code-block:: json

    {
        "schema_version": "1.0",
        "checked_at": "<ISO-8601 UTC>",
        "status": "ok" | "warn" | "fail",
        "details": { ... kind-specific ... }
    }

for the four supported kinds (``live``, ``ready``, ``freshness``, ``deps``).

Design anchors:

* ADR-0029 forbids direct reads against ``core.*`` / ``stg.*`` from
  UI/API paths; the ``freshness`` kind therefore reads ``mart.*`` only
  (via :func:`new_nfl.web.freshness.build_home_overview` — no HTML).
* ADR-0033 isolated Stream A into ``src/new_nfl/observability/`` so the
  Resilience and Hardening streams can land beside us without merge
  conflict.

The module is import-safe on cold DBs: it never forces bootstrap, and the
``ready`` / ``freshness`` / ``deps`` kinds degrade cleanly when tables
are missing (the surface under test is whether the DB is *ready*, so
reporting ``fail`` on missing marts is the correct answer).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import duckdb

from new_nfl.settings import Settings

SCHEMA_VERSION = "1.0"

Kind = Literal["live", "ready", "freshness", "deps"]
SUPPORTED_KINDS: tuple[Kind, ...] = ("live", "ready", "freshness", "deps")
Status = Literal["ok", "warn", "fail"]

# Freshness-row status -> aggregated probe status. The worst row wins.
_FRESHNESS_SEVERITY: dict[str, int] = {
    "ok": 0,
    "stale": 1,
    "warn": 2,
    "fail": 3,
}
_SEVERITY_TO_STATUS: dict[int, Status] = {
    0: "ok",
    1: "warn",
    2: "warn",
    3: "fail",
}


@dataclass(frozen=True)
class HealthResponse:
    schema_version: str
    checked_at: str
    status: Status
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checked_at": self.checked_at,
            "status": self.status,
            "details": self.details,
        }


def _utc_now_iso() -> str:
    # ``datetime.utcnow()`` is naive; emit with an explicit ``Z`` suffix so
    # downstream parsers do not mistake it for local time.
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope(status: Status, details: dict[str, Any]) -> HealthResponse:
    return HealthResponse(
        schema_version=SCHEMA_VERSION,
        checked_at=_utc_now_iso(),
        status=status,
        details=details,
    )


# ---------------------------------------------------------------------------
# live: trivial process check
# ---------------------------------------------------------------------------


def _probe_live() -> HealthResponse:
    """Report that the Python interpreter and module import chain are alive.

    Intentionally does not touch the database — ``live`` is the
    Kubernetes-style "is the process responsive" signal.
    """
    import os

    return _envelope("ok", {"pid": os.getpid()})


# ---------------------------------------------------------------------------
# ready: DB connect + freshness mart presence
# ---------------------------------------------------------------------------


_READY_MART_TABLE = "mart.freshness_overview_v1"


def _probe_ready(settings: Settings) -> HealthResponse:
    """DB is ready iff we can connect *and* the freshness mart exists.

    Mart presence is the gate: the UI read-path relies on
    ``mart.freshness_overview_v1``, so an empty DB that has never seen a
    bootstrap / mart-rebuild must report ``fail``.
    """
    try:
        con = duckdb.connect(str(settings.db_path), read_only=True)
    except duckdb.Error as exc:
        return _envelope(
            "fail",
            {
                "db_path": str(settings.db_path),
                "db_connect": "fail",
                "error": str(exc),
            },
        )
    try:
        try:
            con.execute(f"SELECT 1 FROM {_READY_MART_TABLE} LIMIT 0").fetchall()
            mart_present = True
            error: str | None = None
        except duckdb.Error as exc:
            mart_present = False
            error = str(exc)
    finally:
        con.close()
    status: Status = "ok" if mart_present else "fail"
    details: dict[str, Any] = {
        "db_path": str(settings.db_path),
        "db_connect": "ok",
        "mart_table": _READY_MART_TABLE,
        "mart_present": mart_present,
    }
    if error is not None:
        details["error"] = error
    return _envelope(status, details)


# ---------------------------------------------------------------------------
# freshness: JSON mirror of mart.freshness_overview_v1
# ---------------------------------------------------------------------------


def _probe_freshness(settings: Settings) -> HealthResponse:
    """JSON mirror of :func:`new_nfl.web.freshness.build_home_overview`.

    The read surface is ``mart.freshness_overview_v1`` exclusively
    (ADR-0029). When the mart is absent the downstream service returns
    synthetic ``stale`` rows, which collapse to probe status ``warn``.
    """
    # Local import to keep observability free of web-package coupling at
    # module import time (and to avoid a cycle if web modules later pull
    # observability in).
    from new_nfl.web.freshness import build_home_overview

    overview = build_home_overview(settings)
    rows_detail: list[dict[str, Any]] = []
    worst_severity = 0
    for row in overview.rows:
        last_event_at = (
            row.last_event_at.isoformat() if row.last_event_at is not None else None
        )
        rows_detail.append(
            {
                "domain_schema": row.domain_schema,
                "domain_object": row.domain_object,
                "display_label": row.display_label,
                "display_order": row.display_order,
                "last_event_at": last_event_at,
                "last_event_status": row.last_event_status,
                "last_event_kind": row.last_event_kind,
                "last_ingest_run_id": row.last_ingest_run_id,
                "last_row_count": row.last_row_count,
                "event_count": row.event_count,
                "open_quarantine_count": row.open_quarantine_count,
                "quarantine_max_severity": row.quarantine_max_severity,
                "freshness_status": row.freshness_status,
            }
        )
        worst_severity = max(
            worst_severity,
            _FRESHNESS_SEVERITY.get(row.freshness_status, 1),
        )
    status = _SEVERITY_TO_STATUS.get(worst_severity, "warn")
    details = {
        "mart_table": _READY_MART_TABLE,
        "row_count": len(rows_detail),
        "total_row_count": overview.total_row_count,
        "open_quarantine_count": overview.open_quarantine_count,
        "domains_ok": overview.domains_ok,
        "domains_warn": overview.domains_warn,
        "domains_stale": overview.domains_stale,
        "domains_fail": overview.domains_fail,
        "rows": rows_detail,
    }
    return _envelope(status, details)


# ---------------------------------------------------------------------------
# deps: per-adapter-slice last load_event timestamp
# ---------------------------------------------------------------------------


_LOAD_EVENTS_TABLE = "meta.load_events"


def _probe_deps(settings: Settings) -> HealthResponse:
    """Per adapter-slice, the most recent ``meta.load_events`` timestamp.

    Slice set comes from :data:`new_nfl.adapters.slices.SLICE_REGISTRY`;
    only primary slices (``tier_role='primary'``) with a non-empty
    ``core_table`` are reported — cross-check slices do not land in
    ``core.*`` and have no freshness meaning here.

    Probe aggregates to:

    * ``fail`` — DB cannot be opened
    * ``warn`` — at least one primary slice has zero load events
    * ``ok`` — every primary slice has at least one event
    """
    from new_nfl.adapters.slices import SLICE_REGISTRY

    primary_slices = [
        spec
        for spec in SLICE_REGISTRY.values()
        if spec.tier_role == "primary" and spec.core_table
    ]
    slice_details: list[dict[str, Any]] = []

    try:
        con = duckdb.connect(str(settings.db_path), read_only=True)
    except duckdb.Error as exc:
        return _envelope(
            "fail",
            {
                "db_path": str(settings.db_path),
                "db_connect": "fail",
                "error": str(exc),
                "slice_count": len(primary_slices),
            },
        )
    try:
        try:
            load_events_present = True
            con.execute(f"SELECT 1 FROM {_LOAD_EVENTS_TABLE} LIMIT 0").fetchall()
        except duckdb.Error:
            load_events_present = False

        missing_events = 0
        for spec in primary_slices:
            target_schema, _, target_object = spec.core_table.partition(".")
            last_event_at: str | None = None
            last_event_status: str | None = None
            event_count = 0
            if load_events_present:
                row = con.execute(
                    f"""
                    SELECT MAX(recorded_at), COUNT(*),
                           ARG_MAX(event_status, recorded_at)
                    FROM {_LOAD_EVENTS_TABLE}
                    WHERE target_schema = ? AND target_object = ?
                    """,
                    [target_schema, target_object],
                ).fetchone()
                if row is not None:
                    raw_ts, raw_count, raw_status = row
                    event_count = int(raw_count or 0)
                    if isinstance(raw_ts, datetime):
                        last_event_at = raw_ts.isoformat()
                    elif raw_ts is not None:
                        last_event_at = str(raw_ts)
                    last_event_status = raw_status
            if event_count == 0:
                missing_events += 1
            slice_details.append(
                {
                    "adapter_id": spec.adapter_id,
                    "slice_key": spec.slice_key,
                    "core_table": spec.core_table,
                    "mart_key": spec.mart_key,
                    "last_event_at": last_event_at,
                    "last_event_status": last_event_status,
                    "event_count": event_count,
                }
            )
    finally:
        con.close()

    if not load_events_present:
        status: Status = "fail"
    elif missing_events:
        status = "warn"
    else:
        status = "ok"

    return _envelope(
        status,
        {
            "db_path": str(settings.db_path),
            "load_events_table": _LOAD_EVENTS_TABLE,
            "load_events_present": load_events_present,
            "slice_count": len(primary_slices),
            "slices_without_events": missing_events,
            "slices": slice_details,
        },
    )


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


def build_health_response(settings: Settings, kind: Kind) -> HealthResponse:
    """Return the :class:`HealthResponse` for ``kind``.

    Raises :class:`ValueError` on unknown kinds — the CLI plugin clamps
    the surface via ``choices=`` so this error path is primarily for
    programmatic callers.
    """
    if kind == "live":
        return _probe_live()
    if kind == "ready":
        return _probe_ready(settings)
    if kind == "freshness":
        return _probe_freshness(settings)
    if kind == "deps":
        return _probe_deps(settings)
    raise ValueError(
        f"unknown health-probe kind={kind!r}; "
        f"supported: {list(SUPPORTED_KINDS)}"
    )


def exit_code_for(status: Status) -> int:
    """Map probe ``status`` to a shell-friendly exit code.

    Monitoring callers want ``0`` to mean "all good" and a non-zero
    code to mean "something needs attention"; ``warn`` and ``fail``
    are distinguished so alerting can escalate differently.
    """
    if status == "ok":
        return 0
    if status == "warn":
        return 1
    return 2


__all__ = [
    "HealthResponse",
    "Kind",
    "SCHEMA_VERSION",
    "SUPPORTED_KINDS",
    "Status",
    "build_health_response",
    "exit_code_for",
]
