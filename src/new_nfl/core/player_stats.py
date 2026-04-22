"""Core promotion for ``core.player_stats_weekly`` (T2.5F, ADR-0031).

Snapshot: second aggregating domain. Reads the Tier-A stage
(``stg.nflverse_bulk_player_stats_weekly``) at the ``(season, week, player_id)``
grain and cross-checks every configured Tier-B stage slice at the same grain.
Disagreements on ``passing_yards`` / ``rushing_yards`` / ``receiving_yards`` /
``touchdowns`` open ``meta.quarantine_case`` with
``scope_type='player_stats_weekly'`` and
``scope_ref='PLAYER:SEASON:Wxx'``; the Tier-A value always wins in
``core.player_stats_weekly`` per ADR-0007.

Multi-position players (Taysom Hill and similar) keep one row per
``(season, week, player_id)`` with the rostered ``position`` pinned. When a
player carries stats for multiple positions in the same week (TE + QB), the
dedupe tie-breaker ``_loaded_at DESC`` takes the latest load. Downstream
aggregates sum across all weekly rows for the same ``player_id``, so
multi-position contributions are reflected in season totals.

This promoter also rebuilds all three read projections (weekly passthrough,
season aggregate, career aggregate) so the CLI ``core-load --slice
player_stats_weekly --execute`` exposes the full read surface in one shot.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import duckdb

from new_nfl.adapters.slices import (
    SliceSpec,
    cross_check_slices_for_primary,
    get_slice,
    primary_slice_for_core_table,
)
from new_nfl.jobs.quarantine import open_quarantine_case
from new_nfl.mart.player_stats_career import build_player_stats_career_v1
from new_nfl.mart.player_stats_season import build_player_stats_season_v1
from new_nfl.mart.player_stats_weekly import build_player_stats_weekly_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings

CORE_PLAYER_STATS_WEEKLY_TABLE = "core.player_stats_weekly"

_REQUIRED_TIER_A_COLUMNS: tuple[str, ...] = (
    "season",
    "week",
    "player_id",
)

_CANONICAL_COLUMNS: tuple[str, ...] = (
    "season",
    "week",
    "player_id",
    "team_id",
    "position",
    "passing_yards",
    "passing_tds",
    "interceptions",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "touchdowns",
    "fumbles_lost",
)

# Fields that Tier-B is authoritative *enough* to compare against. Missing
# columns on either side are skipped silently (Tier-B feeds are incomplete
# by design).
_CROSS_CHECK_FIELDS: tuple[str, ...] = (
    "passing_yards",
    "rushing_yards",
    "receiving_yards",
    "touchdowns",
)


@dataclass(frozen=True)
class ConflictRow:
    player_id: str
    season: int
    week: int
    field: str
    tier_a_value: str | None
    tier_b_value: str | None
    tier_b_adapter_id: str

    @property
    def scope_ref(self) -> str:
        return f"{self.player_id}:{self.season}:W{self.week:02d}"


@dataclass(frozen=True)
class CorePlayerStatsLoadResult:
    primary_slice: SliceSpec
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_player_season_week_count: int
    invalid_row_count: int
    conflict_count: int
    opened_quarantine_case_ids: tuple[str, ...]
    cross_check_slice_keys: tuple[str, ...]
    load_event_id: str
    mart_qualified_table: str
    mart_row_count: int
    season_mart_qualified_table: str
    season_mart_row_count: int
    career_mart_qualified_table: str
    career_mart_row_count: int


def _describe_columns(con: duckdb.DuckDBPyConnection, qualified_table: str) -> set[str]:
    try:
        rows = con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f"{qualified_table} does not exist; run stage-load --slice "
            "player_stats_weekly first"
        ) from exc
    return {str(row[0]).strip().lower() for row in rows}


def _assert_required_columns(
    con: duckdb.DuckDBPyConnection,
    qualified_table: str,
    required: Iterable[str],
) -> set[str]:
    present = _describe_columns(con, qualified_table)
    missing = sorted(set(required) - present)
    if missing:
        raise ValueError(
            f"{qualified_table} is missing required player_stats_weekly columns: "
            f"{', '.join(missing)}"
        )
    return present


def _opt(col: str, present: set[str]) -> str:
    return col if col in present else "NULL"


def _profile_tier_a(
    con: duckdb.DuckDBPyConnection, stage_table: str
) -> tuple[int, int, int]:
    source_row_count = int(con.execute(f"SELECT COUNT(*) FROM {stage_table}").fetchone()[0])
    distinct_count = int(
        con.execute(
            f"""
            SELECT COUNT(DISTINCT
                UPPER(TRIM(player_id)) || ':' ||
                COALESCE(CAST(TRY_CAST(season AS INTEGER) AS VARCHAR), '') || ':' ||
                COALESCE(CAST(TRY_CAST(week AS INTEGER) AS VARCHAR), '')
            )
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
              AND TRY_CAST(season AS INTEGER) IS NOT NULL
              AND TRY_CAST(week AS INTEGER) IS NOT NULL
            """
        ).fetchone()[0]
    )
    invalid_row_count = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NULL
               OR TRY_CAST(season AS INTEGER) IS NULL
               OR TRY_CAST(week AS INTEGER) IS NULL
            """
        ).fetchone()[0]
    )
    return source_row_count, distinct_count, invalid_row_count


def _rebuild_core_player_stats_weekly(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    stage_columns: set[str],
) -> int:
    team_id = _opt("team_id", stage_columns)
    position = _opt("position", stage_columns)
    passing_yards = _opt("passing_yards", stage_columns)
    passing_tds = _opt("passing_tds", stage_columns)
    interceptions = _opt("interceptions", stage_columns)
    rushing_yards = _opt("rushing_yards", stage_columns)
    rushing_tds = _opt("rushing_tds", stage_columns)
    receptions = _opt("receptions", stage_columns)
    receiving_yards = _opt("receiving_yards", stage_columns)
    receiving_tds = _opt("receiving_tds", stage_columns)
    touchdowns = _opt("touchdowns", stage_columns)
    fumbles_lost = _opt("fumbles_lost", stage_columns)
    loaded_at = "_loaded_at" if "_loaded_at" in stage_columns else "NULL"
    source_file_id = "_source_file_id" if "_source_file_id" in stage_columns else "NULL"
    adapter_id = "_adapter_id" if "_adapter_id" in stage_columns else "NULL"

    con.execute("CREATE SCHEMA IF NOT EXISTS core")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {CORE_PLAYER_STATS_WEEKLY_TABLE} AS
        WITH ranked AS (
            SELECT
                TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER) AS season,
                TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER) AS week,
                UPPER(TRIM(player_id)) AS player_id,
                UPPER(NULLIF(TRIM(CAST({team_id} AS VARCHAR)), '')) AS team_id,
                UPPER(NULLIF(TRIM(CAST({position} AS VARCHAR)), '')) AS position,
                TRY_CAST(NULLIF(TRIM(CAST({passing_yards} AS VARCHAR)), '') AS INTEGER)
                    AS passing_yards,
                TRY_CAST(NULLIF(TRIM(CAST({passing_tds} AS VARCHAR)), '') AS INTEGER)
                    AS passing_tds,
                TRY_CAST(NULLIF(TRIM(CAST({interceptions} AS VARCHAR)), '') AS INTEGER)
                    AS interceptions,
                TRY_CAST(NULLIF(TRIM(CAST({rushing_yards} AS VARCHAR)), '') AS INTEGER)
                    AS rushing_yards,
                TRY_CAST(NULLIF(TRIM(CAST({rushing_tds} AS VARCHAR)), '') AS INTEGER)
                    AS rushing_tds,
                TRY_CAST(NULLIF(TRIM(CAST({receptions} AS VARCHAR)), '') AS INTEGER)
                    AS receptions,
                TRY_CAST(NULLIF(TRIM(CAST({receiving_yards} AS VARCHAR)), '') AS INTEGER)
                    AS receiving_yards,
                TRY_CAST(NULLIF(TRIM(CAST({receiving_tds} AS VARCHAR)), '') AS INTEGER)
                    AS receiving_tds,
                TRY_CAST(NULLIF(TRIM(CAST({touchdowns} AS VARCHAR)), '') AS INTEGER)
                    AS touchdowns,
                TRY_CAST(NULLIF(TRIM(CAST({fumbles_lost} AS VARCHAR)), '') AS INTEGER)
                    AS fumbles_lost,
                COALESCE({source_file_id}, '') AS _source_file_id,
                COALESCE({adapter_id}, '') AS _adapter_id,
                {loaded_at} AS _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER),
                        TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER),
                        UPPER(TRIM(player_id))
                    ORDER BY {loaded_at} DESC NULLS LAST, {source_file_id} DESC
                ) AS _rn
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
              AND TRY_CAST(season AS INTEGER) IS NOT NULL
              AND TRY_CAST(week AS INTEGER) IS NOT NULL
        )
        SELECT
            season,
            week,
            player_id,
            team_id,
            position,
            passing_yards,
            passing_tds,
            interceptions,
            rushing_yards,
            rushing_tds,
            receptions,
            receiving_yards,
            receiving_tds,
            touchdowns,
            fumbles_lost,
            _source_file_id,
            _adapter_id,
            CURRENT_TIMESTAMP AS _canonicalized_at
        FROM ranked
        WHERE _rn = 1
        """
    )
    return int(
        con.execute(
            f"SELECT COUNT(*) FROM {CORE_PLAYER_STATS_WEEKLY_TABLE}"
        ).fetchone()[0]
    )


def _detect_conflicts(
    con: duckdb.DuckDBPyConnection,
    *,
    tier_a_columns: set[str],
    cross_check_slices: list[SliceSpec],
) -> list[ConflictRow]:
    conflicts: list[ConflictRow] = []
    for spec in cross_check_slices:
        try:
            tier_b_columns = _describe_columns(con, spec.stage_qualified_table)
        except ValueError:
            continue
        if not {"season", "week", "player_id"}.issubset(tier_b_columns):
            continue
        comparable = [
            field
            for field in _CROSS_CHECK_FIELDS
            if field in tier_a_columns and field in tier_b_columns
        ]
        for field in comparable:
            rows = con.execute(
                f"""
                SELECT
                    a.player_id AS player_id,
                    a.season AS season,
                    a.week AS week,
                    CAST(a.{field} AS VARCHAR) AS tier_a_value,
                    CAST(TRY_CAST(CAST(b.{field} AS VARCHAR) AS INTEGER) AS VARCHAR)
                        AS tier_b_value
                FROM {CORE_PLAYER_STATS_WEEKLY_TABLE} a
                JOIN {spec.stage_qualified_table} b
                  ON UPPER(TRIM(b.player_id)) = a.player_id
                 AND TRY_CAST(b.season AS INTEGER) = a.season
                 AND TRY_CAST(b.week AS INTEGER) = a.week
                WHERE a.{field} IS NOT NULL
                  AND TRY_CAST(CAST(b.{field} AS VARCHAR) AS INTEGER) IS NOT NULL
                  AND a.{field} <> TRY_CAST(CAST(b.{field} AS VARCHAR) AS INTEGER)
                ORDER BY player_id, season, week
                """
            ).fetchall()
            for player_id, season, week, tier_a_value, tier_b_value in rows:
                conflicts.append(
                    ConflictRow(
                        player_id=str(player_id),
                        season=int(season),
                        week=int(week),
                        field=field,
                        tier_a_value=tier_a_value,
                        tier_b_value=tier_b_value,
                        tier_b_adapter_id=spec.adapter_id,
                    )
                )
    return conflicts


def _open_conflict_quarantine(
    settings: Settings,
    *,
    ingest_run_id: str,
    primary: SliceSpec,
    conflicts: list[ConflictRow],
) -> list[str]:
    by_scope: dict[str, list[ConflictRow]] = {}
    for c in conflicts:
        by_scope.setdefault(c.scope_ref, []).append(c)
    case_ids: list[str] = []
    for scope_ref, scope_conflicts in sorted(by_scope.items()):
        evidence = [
            {
                "field": c.field,
                "tier_a_value": c.tier_a_value,
                "tier_b_value": c.tier_b_value,
                "tier_b_adapter_id": c.tier_b_adapter_id,
                "tier_a_adapter_id": primary.adapter_id,
                "ingest_run_id": ingest_run_id,
            }
            for c in scope_conflicts
        ]
        case = open_quarantine_case(
            settings,
            scope_type="player_stats_weekly",
            scope_ref=scope_ref,
            reason_code="tier_b_disagreement",
            severity="warning",
            evidence_refs=evidence,
            notes=(
                f"Tier-A ({primary.adapter_id}) vs Tier-B disagreement on "
                f"{len(scope_conflicts)} field(s) for {scope_ref}; Tier-A "
                "value wins in core.player_stats_weekly."
            ),
        )
        case_ids.append(case.quarantine_case_id)
    return case_ids


def execute_core_player_stats_load(
    settings: Settings,
    *,
    execute: bool,
) -> CorePlayerStatsLoadResult:
    primary = primary_slice_for_core_table(CORE_PLAYER_STATS_WEEKLY_TABLE)
    if primary is None:
        primary = get_slice("nflverse_bulk", "player_stats_weekly")
    cross_checks = cross_check_slices_for_primary(primary)
    pipeline_name = f"adapter.{primary.adapter_id}.core_load.player_stats_weekly"

    con = duckdb.connect(str(settings.db_path))
    try:
        tier_a_columns = _assert_required_columns(
            con, primary.stage_qualified_table, _REQUIRED_TIER_A_COLUMNS
        )
        source_row_count, distinct_count, invalid_row_count = _profile_tier_a(
            con, primary.stage_qualified_table
        )
        if not execute:
            return CorePlayerStatsLoadResult(
                primary_slice=primary,
                run_mode="dry_run",
                run_status="planned_core_player_stats_load",
                pipeline_name=pipeline_name,
                ingest_run_id="",
                qualified_table=CORE_PLAYER_STATS_WEEKLY_TABLE,
                source_row_count=source_row_count,
                row_count=0,
                distinct_player_season_week_count=distinct_count,
                invalid_row_count=invalid_row_count,
                conflict_count=0,
                opened_quarantine_case_ids=(),
                cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
                load_event_id="",
                mart_qualified_table="",
                mart_row_count=0,
                season_mart_qualified_table="",
                season_mart_row_count=0,
                career_mart_qualified_table="",
                career_mart_row_count=0,
            )
        row_count = _rebuild_core_player_stats_weekly(
            con, primary.stage_qualified_table, tier_a_columns
        )
        conflicts = _detect_conflicts(
            con,
            tier_a_columns=tier_a_columns,
            cross_check_slices=cross_checks,
        )
    finally:
        con.close()

    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        adapter_id=primary.adapter_id,
        run_mode="execute",
        run_status="core_player_stats_weekly_loaded",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=1,
        message="T2.5F core.player_stats_weekly promotion",
    )
    opened_case_ids = _open_conflict_quarantine(
        settings,
        ingest_run_id=ingest_run_id,
        primary=primary,
        conflicts=conflicts,
    )
    weekly_mart = build_player_stats_weekly_v1(settings)
    season_mart = build_player_stats_season_v1(settings)
    career_mart = build_player_stats_career_v1(settings)
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=primary.adapter_id,
        pipeline_name=pipeline_name,
        event_kind="core_loaded",
        target_schema="core",
        target_object="player_stats_weekly",
        row_count=row_count,
        object_path=primary.stage_qualified_table,
        payload={
            "source_table": primary.stage_qualified_table,
            "qualified_table": CORE_PLAYER_STATS_WEEKLY_TABLE,
            "source_row_count": source_row_count,
            "distinct_player_season_week_count": distinct_count,
            "invalid_row_count": invalid_row_count,
            "row_count": row_count,
            "conflict_count": len(conflicts),
            "opened_quarantine_case_ids": opened_case_ids,
            "weekly_mart_qualified_table": weekly_mart.qualified_table,
            "weekly_mart_row_count": weekly_mart.row_count,
            "season_mart_qualified_table": season_mart.qualified_table,
            "season_mart_row_count": season_mart.row_count,
            "career_mart_qualified_table": career_mart.qualified_table,
            "career_mart_row_count": career_mart.row_count,
        },
    )
    return CorePlayerStatsLoadResult(
        primary_slice=primary,
        run_mode="execute",
        run_status="core_player_stats_weekly_loaded",
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        qualified_table=CORE_PLAYER_STATS_WEEKLY_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_player_season_week_count=distinct_count,
        invalid_row_count=invalid_row_count,
        conflict_count=len(conflicts),
        opened_quarantine_case_ids=tuple(opened_case_ids),
        cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
        load_event_id=load_event_id,
        mart_qualified_table=weekly_mart.qualified_table,
        mart_row_count=weekly_mart.row_count,
        season_mart_qualified_table=season_mart.qualified_table,
        season_mart_row_count=season_mart.row_count,
        career_mart_qualified_table=career_mart.qualified_table,
        career_mart_row_count=career_mart.row_count,
    )


__all__ = [
    "CORE_PLAYER_STATS_WEEKLY_TABLE",
    "ConflictRow",
    "CorePlayerStatsLoadResult",
    "execute_core_player_stats_load",
]
