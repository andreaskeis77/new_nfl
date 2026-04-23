"""Mart builder for ``mart.provenance_v1`` (T2.6G, ADR-0029).

Per-scope provenance projection. One row per ``(scope_type, scope_ref)``
where ``scope_type`` is the domain keyword used elsewhere in the pipeline
(``team``, ``game``, ``player``, ``roster_membership``,
``team_stats_weekly``, ``player_stats_weekly``) and ``scope_ref`` is the
canonical domain key as constructed by the core-load layer.

Two projections feed the mart:

* **Source coverage** — aggregated from the per-domain ``core.*`` tables
  by their ``source_file_id`` / ``source_adapter_id`` /
  ``source_canonicalized_at`` columns. Reports which adapter slice +
  ingest run produced each canonical row, the earliest observation and
  the latest canonicalisation stamp.

* **Quarantine stream** — aggregated from ``meta.quarantine_case`` by
  ``scope_type`` + ``scope_ref``. Reports total cases, how many remain
  open, the last severity and the reason code of the most recent case
  in window.

The projection is a full rebuild via ``CREATE OR REPLACE TABLE`` and is
defensive against missing upstream tables: if any individual ``core.*``
domain is absent the contributing UNION branch is skipped rather than
failing the build. That mirrors the cold-start discipline of the other
aggregating marts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.settings import Settings

MART_PROVENANCE_V1 = "mart.provenance_v1"
_SOURCE_TABLE = "meta.quarantine_case"

_CORE_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("team", "core.team", "team_id"),
    ("game", "core.game", "game_id"),
    ("player", "core.player", "player_id"),
    (
        "roster_membership",
        "core.roster_membership",
        "player_id || ':' || team_id || ':' || CAST(season AS VARCHAR) || "
        "':W' || LPAD(CAST(valid_from_week AS VARCHAR), 2, '0')",
    ),
    (
        "team_stats_weekly",
        "core.team_stats_weekly",
        "team_id || ':' || CAST(season AS VARCHAR) || "
        "':W' || LPAD(CAST(week AS VARCHAR), 2, '0')",
    ),
    (
        "player_stats_weekly",
        "core.player_stats_weekly",
        "player_id || ':' || CAST(season AS VARCHAR) || "
        "':W' || LPAD(CAST(week AS VARCHAR), 2, '0')",
    ),
)


@dataclass(frozen=True)
class MartProvenanceResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    built_at: datetime


def _table_exists(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return False
    return True


def _ensure_metadata_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create minimal stubs so the builder can be invoked on a fresh DB."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.quarantine_case (
            quarantine_case_id VARCHAR,
            scope_type VARCHAR,
            scope_ref VARCHAR,
            reason_code VARCHAR,
            severity VARCHAR,
            status VARCHAR,
            first_seen_at TIMESTAMP,
            last_seen_at TIMESTAMP,
            resolved_at TIMESTAMP
        )
        """
    )


def _build_source_union(con: duckdb.DuckDBPyConnection) -> str:
    """Return a UNION ALL of (scope_type, scope_ref, source_*) per domain.

    Only includes domains whose ``core.*`` table exists; if none exist the
    caller must fall back to an empty projection.
    """
    branches: list[str] = []
    for scope_type, qualified, ref_expr in _CORE_SOURCES:
        if not _table_exists(con, qualified):
            continue
        branches.append(
            f"""
            SELECT
                '{scope_type}' AS scope_type,
                {ref_expr} AS scope_ref,
                source_file_id,
                source_adapter_id,
                source_canonicalized_at
            FROM {qualified}
            WHERE source_file_id IS NOT NULL
              OR source_adapter_id IS NOT NULL
            """
        )
    if not branches:
        return (
            "SELECT CAST(NULL AS VARCHAR) AS scope_type, "
            "CAST(NULL AS VARCHAR) AS scope_ref, "
            "CAST(NULL AS VARCHAR) AS source_file_id, "
            "CAST(NULL AS VARCHAR) AS source_adapter_id, "
            "CAST(NULL AS TIMESTAMP) AS source_canonicalized_at "
            "WHERE FALSE"
        )
    return " UNION ALL ".join(branches)


@register_mart_builder("provenance_v1")
def build_provenance_v1(settings: Settings) -> MartProvenanceResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        _ensure_metadata_tables(con)
        source_union_sql = _build_source_union(con)
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_PROVENANCE_V1} AS
            WITH scope_source AS (
                {source_union_sql}
            ),
            source_agg AS (
                SELECT
                    scope_type,
                    scope_ref,
                    LIST(DISTINCT source_file_id) FILTER (
                        WHERE source_file_id IS NOT NULL
                    ) AS source_file_ids,
                    LIST(DISTINCT source_adapter_id) FILTER (
                        WHERE source_adapter_id IS NOT NULL
                    ) AS source_adapter_ids,
                    MIN(source_canonicalized_at) AS first_seen_at,
                    MAX(source_canonicalized_at) AS last_canonicalized_at,
                    COUNT(*) AS source_row_count
                FROM scope_source
                WHERE scope_type IS NOT NULL
                GROUP BY scope_type, scope_ref
            ),
            quarantine_agg AS (
                SELECT
                    scope_type,
                    scope_ref,
                    COUNT(*) AS quarantine_case_count,
                    SUM(CASE
                        WHEN status NOT IN ('resolved', 'closed', 'dismissed')
                          OR status IS NULL
                        THEN 1 ELSE 0
                    END) AS open_quarantine_count,
                    ARG_MAX(reason_code, last_seen_at) AS last_reason_code,
                    ARG_MAX(severity, last_seen_at) AS last_severity,
                    ARG_MAX(status, last_seen_at) AS last_status,
                    MAX(last_seen_at) AS last_quarantine_at
                FROM meta.quarantine_case
                GROUP BY scope_type, scope_ref
            ),
            all_scopes AS (
                SELECT scope_type, scope_ref FROM source_agg
                UNION
                SELECT scope_type, scope_ref FROM quarantine_agg
            )
            SELECT
                a.scope_type,
                a.scope_ref,
                LOWER(a.scope_type) AS scope_type_lower,
                LOWER(a.scope_ref) AS scope_ref_lower,
                COALESCE(s.source_file_ids, CAST([] AS VARCHAR[])) AS source_file_ids,
                COALESCE(s.source_adapter_ids, CAST([] AS VARCHAR[])) AS source_adapter_ids,
                s.first_seen_at,
                s.last_canonicalized_at,
                COALESCE(s.source_row_count, 0) AS source_row_count,
                COALESCE(q.quarantine_case_count, 0) AS quarantine_case_count,
                COALESCE(q.open_quarantine_count, 0) AS open_quarantine_count,
                q.last_reason_code,
                q.last_severity,
                q.last_status,
                q.last_quarantine_at,
                CASE
                    WHEN COALESCE(q.open_quarantine_count, 0) > 0 THEN 'warn'
                    WHEN COALESCE(s.source_row_count, 0) = 0
                      AND COALESCE(q.quarantine_case_count, 0) = 0 THEN 'unknown'
                    ELSE 'ok'
                END AS provenance_status,
                CURRENT_TIMESTAMP AS built_at
            FROM all_scopes a
            LEFT JOIN source_agg s USING (scope_type, scope_ref)
            LEFT JOIN quarantine_agg q USING (scope_type, scope_ref)
            WHERE a.scope_type IS NOT NULL
              AND a.scope_ref IS NOT NULL
            ORDER BY a.scope_type, a.scope_ref
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_PROVENANCE_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    built_at = datetime.now()
    return MartProvenanceResult(
        qualified_table=MART_PROVENANCE_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=built_at,
    )


__all__ = [
    "MART_PROVENANCE_V1",
    "MartProvenanceResult",
    "build_provenance_v1",
]
