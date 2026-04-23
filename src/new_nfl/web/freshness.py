"""Read service for ``mart.freshness_overview_v1`` (T2.6B, ADR-0029).

Pulls per-domain freshness rows from the mart and shapes them into
dataclasses the Home template consumes. No SQL joins to ``core.*`` or
``stg.*``; if the mart is absent, the service returns a synthetic
``stale`` row per expected domain so the Home tiles still render.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_TABLE = "mart.freshness_overview_v1"

_EXPECTED_DOMAINS: tuple[tuple[str, str, str, int], ...] = (
    ("core", "team", "Teams", 1),
    ("core", "game", "Games", 2),
    ("core", "player", "Players", 3),
    ("core", "roster_membership", "Rosters", 4),
    ("core", "team_stats_weekly", "Team Stats (weekly)", 5),
    ("core", "player_stats_weekly", "Player Stats (weekly)", 6),
)


@dataclass(frozen=True)
class FreshnessRow:
    domain_schema: str
    domain_object: str
    display_label: str
    display_order: int
    last_event_at: datetime | None
    last_event_status: str | None
    last_event_kind: str | None
    last_ingest_run_id: str | None
    last_row_count: int | None
    event_count: int
    open_quarantine_count: int
    quarantine_max_severity: str | None
    freshness_status: str


@dataclass(frozen=True)
class HomeOverview:
    rows: tuple[FreshnessRow, ...]
    total_row_count: int
    open_quarantine_count: int
    domains_ok: int
    domains_warn: int
    domains_stale: int
    domains_fail: int

    @property
    def is_empty(self) -> bool:
        return self.total_row_count == 0


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


def _synthetic_stale_rows() -> tuple[FreshnessRow, ...]:
    return tuple(
        FreshnessRow(
            domain_schema=schema,
            domain_object=obj,
            display_label=label,
            display_order=order,
            last_event_at=None,
            last_event_status=None,
            last_event_kind=None,
            last_ingest_run_id=None,
            last_row_count=None,
            event_count=0,
            open_quarantine_count=0,
            quarantine_max_severity=None,
            freshness_status="stale",
        )
        for schema, obj, label, order in _EXPECTED_DOMAINS
    )


def _badge_status_for(freshness_status: str) -> str:
    return {
        "ok": "success",
        "warn": "warn",
        "fail": "danger",
        "stale": "neutral",
    }.get(freshness_status, "neutral")


def load_freshness_rows(settings: Settings) -> tuple[FreshnessRow, ...]:
    con = duckdb.connect(str(settings.db_path), read_only=False)
    try:
        try:
            raw = con.execute(
                f"""
                SELECT
                    domain_schema,
                    domain_object,
                    display_label,
                    display_order,
                    last_event_at,
                    last_event_status,
                    last_event_kind,
                    last_ingest_run_id,
                    last_row_count,
                    event_count,
                    open_quarantine_count,
                    quarantine_max_severity,
                    freshness_status
                FROM {_MART_TABLE}
                ORDER BY display_order
                """
            ).fetchall()
        except duckdb.Error:
            return _synthetic_stale_rows()
    finally:
        con.close()
    rows = tuple(
        FreshnessRow(
            domain_schema=r[0],
            domain_object=r[1],
            display_label=r[2],
            display_order=int(r[3]),
            last_event_at=_coerce_datetime(r[4]),
            last_event_status=r[5],
            last_event_kind=r[6],
            last_ingest_run_id=r[7],
            last_row_count=int(r[8]) if r[8] is not None else None,
            event_count=int(r[9]) if r[9] is not None else 0,
            open_quarantine_count=int(r[10]) if r[10] is not None else 0,
            quarantine_max_severity=r[11],
            freshness_status=r[12] or "stale",
        )
        for r in raw
    )
    if not rows:
        return _synthetic_stale_rows()
    return rows


def build_home_overview(settings: Settings) -> HomeOverview:
    rows = load_freshness_rows(settings)
    total = sum(r.last_row_count or 0 for r in rows)
    open_q = sum(r.open_quarantine_count for r in rows)
    ok = sum(1 for r in rows if r.freshness_status == "ok")
    warn = sum(1 for r in rows if r.freshness_status == "warn")
    stale = sum(1 for r in rows if r.freshness_status == "stale")
    fail = sum(1 for r in rows if r.freshness_status == "fail")
    return HomeOverview(
        rows=rows,
        total_row_count=total,
        open_quarantine_count=open_q,
        domains_ok=ok,
        domains_warn=warn,
        domains_stale=stale,
        domains_fail=fail,
    )


def overview_to_template_context(overview: HomeOverview) -> dict[str, Any]:
    stat_tiles = (
        {
            "label": "Domänen grün",
            "value": overview.domains_ok,
            "delta": None,
            "delta_status": None,
        },
        {
            "label": "Domänen stale",
            "value": overview.domains_stale,
            "delta": None,
            "delta_status": "warn" if overview.domains_stale else None,
        },
        {
            "label": "Domänen warn/fail",
            "value": overview.domains_warn + overview.domains_fail,
            "delta": None,
            "delta_status": (
                "danger"
                if overview.domains_fail
                else ("warn" if overview.domains_warn else None)
            ),
        },
        {
            "label": "Offene Quarantäne",
            "value": overview.open_quarantine_count,
            "delta": None,
            "delta_status": "danger" if overview.open_quarantine_count else None,
        },
    )
    freshness_sample = tuple(
        {
            "domain": row.display_label,
            "updated_at": row.last_event_at,
            "status": _badge_status_for(row.freshness_status),
            "open_quarantine_count": row.open_quarantine_count,
            "last_row_count": row.last_row_count,
        }
        for row in overview.rows
    )
    return {
        "hero": {
            "title": "NEW NFL",
            "subtitle": "Private Analytics Platform",
        },
        "stat_tiles": stat_tiles,
        "freshness_sample": freshness_sample,
        "overview": overview,
    }


__all__ = [
    "FreshnessRow",
    "HomeOverview",
    "build_home_overview",
    "load_freshness_rows",
    "overview_to_template_context",
]
