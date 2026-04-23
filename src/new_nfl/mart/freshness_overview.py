"""Mart builder for ``mart.freshness_overview_v1`` (T2.6B, ADR-0029).

Per-domain freshness projection derived from ``meta.load_events`` and
``meta.quarantine_case``. This is the read surface the Home/Freshness
dashboard consumes; it must not depend on ``core.*`` or ``stg.*``.

The mart lists every *expected* core domain (``team``, ``game``,
``player``, ``roster_membership``, ``team_stats_weekly``,
``player_stats_weekly``) so the UI can render a stable 6-tile grid even
before any load has happened (``last_event_at`` is then ``NULL`` and the
``freshness_status`` column collapses to ``'stale'``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.settings import Settings

MART_FRESHNESS_OVERVIEW_V1 = "mart.freshness_overview_v1"
_SOURCE_TABLE = "meta.load_events"

EXPECTED_CORE_DOMAINS: tuple[tuple[str, str, str, int], ...] = (
    ("core", "team", "Teams", 1),
    ("core", "game", "Games", 2),
    ("core", "player", "Players", 3),
    ("core", "roster_membership", "Rosters", 4),
    ("core", "team_stats_weekly", "Team Stats (weekly)", 5),
    ("core", "player_stats_weekly", "Player Stats (weekly)", 6),
)


@dataclass(frozen=True)
class MartFreshnessOverviewResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    built_at: datetime


def _ensure_metadata_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create minimal no-op projections if the meta surface is absent.

    Freshness is a read-only aggregate, so the builder tolerates the
    absence of metadata tables by treating them as empty. This keeps the
    mart rebuildable on a brand-new DB where only bootstrap has run.
    """
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.load_events (
            load_event_id VARCHAR,
            ingest_run_id VARCHAR,
            target_schema VARCHAR,
            target_object VARCHAR,
            event_kind VARCHAR,
            event_status VARCHAR,
            row_count BIGINT,
            recorded_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.quarantine_case (
            quarantine_case_id VARCHAR,
            scope_type VARCHAR,
            scope_ref VARCHAR,
            severity VARCHAR,
            status VARCHAR,
            last_seen_at TIMESTAMP
        )
        """
    )


def _expected_domains_values_clause() -> str:
    rows = ", ".join(
        f"('{schema}', '{obj}', '{label}', {order})"
        for schema, obj, label, order in EXPECTED_CORE_DOMAINS
    )
    return f"(VALUES {rows}) AS d(target_schema, target_object, display_label, display_order)"


def build_freshness_overview_v1(settings: Settings) -> MartFreshnessOverviewResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        _ensure_metadata_tables(con)
        source_row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {_SOURCE_TABLE} WHERE target_schema = 'core'"
            ).fetchone()[0]
        )
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_FRESHNESS_OVERVIEW_V1} AS
            WITH last_event AS (
                SELECT
                    target_schema,
                    target_object,
                    ARG_MAX(ingest_run_id, recorded_at) AS last_ingest_run_id,
                    ARG_MAX(event_kind, recorded_at) AS last_event_kind,
                    ARG_MAX(event_status, recorded_at) AS last_event_status,
                    ARG_MAX(row_count, recorded_at) AS last_row_count,
                    MAX(recorded_at) AS last_event_at,
                    COUNT(*) AS event_count
                FROM meta.load_events
                WHERE target_schema = 'core'
                GROUP BY target_schema, target_object
            ),
            open_q AS (
                SELECT
                    scope_type,
                    COUNT(*) AS open_quarantine_count,
                    MAX(severity) AS quarantine_max_severity,
                    MAX(last_seen_at) AS quarantine_last_seen_at
                FROM meta.quarantine_case
                WHERE status NOT IN ('resolved', 'closed', 'dismissed')
                GROUP BY scope_type
            )
            SELECT
                d.target_schema AS domain_schema,
                d.target_object AS domain_object,
                d.display_label,
                d.display_order,
                le.last_event_at,
                le.last_event_status,
                le.last_event_kind,
                le.last_ingest_run_id,
                le.last_row_count,
                COALESCE(le.event_count, 0) AS event_count,
                COALESCE(q.open_quarantine_count, 0) AS open_quarantine_count,
                q.quarantine_max_severity,
                q.quarantine_last_seen_at,
                CASE
                    WHEN le.last_event_at IS NULL THEN 'stale'
                    WHEN le.last_event_status = 'failed' THEN 'fail'
                    WHEN COALESCE(q.open_quarantine_count, 0) > 0 THEN 'warn'
                    ELSE 'ok'
                END AS freshness_status,
                CURRENT_TIMESTAMP AS built_at
            FROM {_expected_domains_values_clause()}
            LEFT JOIN last_event le
              ON le.target_schema = d.target_schema
             AND le.target_object = d.target_object
            LEFT JOIN open_q q
              ON q.scope_type = d.target_object
            ORDER BY d.display_order
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_FRESHNESS_OVERVIEW_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    built_at = datetime.now()
    return MartFreshnessOverviewResult(
        qualified_table=MART_FRESHNESS_OVERVIEW_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=built_at,
    )


__all__ = [
    "EXPECTED_CORE_DOMAINS",
    "MART_FRESHNESS_OVERVIEW_V1",
    "MartFreshnessOverviewResult",
    "build_freshness_overview_v1",
]
