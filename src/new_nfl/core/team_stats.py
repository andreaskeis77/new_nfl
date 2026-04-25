"""Core promotion for ``core.team_stats_weekly`` (T2.5E, ADR-0031).

Snapshot: first aggregating domain. Reads the Tier-A stage
(``stg.nflverse_bulk_team_stats_weekly``) at the ``(season, week, team_id)``
grain and cross-checks every configured Tier-B stage slice at the same grain.
Disagreements on ``points_for`` / ``points_against`` / ``yards_for`` /
``turnovers`` open ``meta.quarantine_case`` with
``scope_type='team_stats_weekly'`` and
``scope_ref='TEAM:SEASON:Wxx'``; the Tier-A value always wins in
``core.team_stats_weekly`` per ADR-0007.

This promoter also rebuilds both read projections (the weekly passthrough
and the season aggregate) so the CLI ``core-load --slice team_stats_weekly
--execute`` exposes both marts in one shot.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import duckdb

from new_nfl.adapters.column_aliases import apply_column_aliases
from new_nfl.adapters.slices import (
    SliceSpec,
    cross_check_slices_for_primary,
    get_slice,
    primary_slice_for_core_table,
)
from new_nfl.jobs.quarantine import open_quarantine_case
from new_nfl.mart.team_stats_season import build_team_stats_season_v1
from new_nfl.mart.team_stats_weekly import build_team_stats_weekly_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings

CORE_TEAM_STATS_WEEKLY_TABLE = "core.team_stats_weekly"

_REQUIRED_TIER_A_COLUMNS: tuple[str, ...] = (
    "season",
    "week",
    "team_id",
)

_CANONICAL_COLUMNS: tuple[str, ...] = (
    "season",
    "week",
    "team_id",
    "opponent_team_id",
    "points_for",
    "points_against",
    "yards_for",
    "yards_against",
    "turnovers",
    "penalties_for",
)

# Fields that Tier-B is authoritative *enough* to compare against. Missing
# columns on either side are skipped silently (Tier-B feeds are incomplete
# by design).
_CROSS_CHECK_FIELDS: tuple[str, ...] = (
    "points_for",
    "points_against",
    "yards_for",
    "turnovers",
)


@dataclass(frozen=True)
class ConflictRow:
    team_id: str
    season: int
    week: int
    field: str
    tier_a_value: str | None
    tier_b_value: str | None
    tier_b_adapter_id: str

    @property
    def scope_ref(self) -> str:
        return f"{self.team_id}:{self.season}:W{self.week:02d}"


@dataclass(frozen=True)
class CoreTeamStatsLoadResult:
    primary_slice: SliceSpec
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_team_season_week_count: int
    invalid_row_count: int
    conflict_count: int
    opened_quarantine_case_ids: tuple[str, ...]
    cross_check_slice_keys: tuple[str, ...]
    load_event_id: str
    mart_qualified_table: str
    mart_row_count: int
    season_mart_qualified_table: str
    season_mart_row_count: int


def _describe_columns(con: duckdb.DuckDBPyConnection, qualified_table: str) -> set[str]:
    try:
        rows = con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f"{qualified_table} does not exist; run stage-load --slice "
            "team_stats_weekly first"
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
            f"{qualified_table} is missing required team_stats_weekly columns: "
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
                UPPER(TRIM(team_id)) || ':' ||
                COALESCE(CAST(TRY_CAST(season AS INTEGER) AS VARCHAR), '') || ':' ||
                COALESCE(CAST(TRY_CAST(week AS INTEGER) AS VARCHAR), '')
            )
            FROM {stage_table}
            WHERE NULLIF(TRIM(team_id), '') IS NOT NULL
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
            WHERE NULLIF(TRIM(team_id), '') IS NULL
               OR TRY_CAST(season AS INTEGER) IS NULL
               OR TRY_CAST(week AS INTEGER) IS NULL
            """
        ).fetchone()[0]
    )
    return source_row_count, distinct_count, invalid_row_count


def _rebuild_core_team_stats_weekly(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    stage_columns: set[str],
) -> int:
    opponent = _opt("opponent_team_id", stage_columns)
    points_for = _opt("points_for", stage_columns)
    points_against = _opt("points_against", stage_columns)
    yards_for = _opt("yards_for", stage_columns)
    yards_against = _opt("yards_against", stage_columns)
    turnovers = _opt("turnovers", stage_columns)
    penalties_for = _opt("penalties_for", stage_columns)
    loaded_at = "_loaded_at" if "_loaded_at" in stage_columns else "NULL"
    source_file_id = "_source_file_id" if "_source_file_id" in stage_columns else "NULL"
    adapter_id = "_adapter_id" if "_adapter_id" in stage_columns else "NULL"

    con.execute("CREATE SCHEMA IF NOT EXISTS core")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {CORE_TEAM_STATS_WEEKLY_TABLE} AS
        WITH ranked AS (
            SELECT
                TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER) AS season,
                TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER) AS week,
                UPPER(TRIM(team_id)) AS team_id,
                UPPER(NULLIF(TRIM(CAST({opponent} AS VARCHAR)), '')) AS opponent_team_id,
                TRY_CAST(NULLIF(TRIM(CAST({points_for} AS VARCHAR)), '') AS INTEGER)
                    AS points_for,
                TRY_CAST(NULLIF(TRIM(CAST({points_against} AS VARCHAR)), '') AS INTEGER)
                    AS points_against,
                TRY_CAST(NULLIF(TRIM(CAST({yards_for} AS VARCHAR)), '') AS INTEGER)
                    AS yards_for,
                TRY_CAST(NULLIF(TRIM(CAST({yards_against} AS VARCHAR)), '') AS INTEGER)
                    AS yards_against,
                TRY_CAST(NULLIF(TRIM(CAST({turnovers} AS VARCHAR)), '') AS INTEGER)
                    AS turnovers,
                TRY_CAST(NULLIF(TRIM(CAST({penalties_for} AS VARCHAR)), '') AS INTEGER)
                    AS penalties_for,
                COALESCE({source_file_id}, '') AS _source_file_id,
                COALESCE({adapter_id}, '') AS _adapter_id,
                {loaded_at} AS _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER),
                        TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER),
                        UPPER(TRIM(team_id))
                    ORDER BY {loaded_at} DESC NULLS LAST, {source_file_id} DESC
                ) AS _rn
            FROM {stage_table}
            WHERE NULLIF(TRIM(team_id), '') IS NOT NULL
              AND TRY_CAST(season AS INTEGER) IS NOT NULL
              AND TRY_CAST(week AS INTEGER) IS NOT NULL
        )
        SELECT
            season,
            week,
            team_id,
            opponent_team_id,
            points_for,
            points_against,
            yards_for,
            yards_against,
            turnovers,
            penalties_for,
            _source_file_id,
            _adapter_id,
            CURRENT_TIMESTAMP AS _canonicalized_at
        FROM ranked
        WHERE _rn = 1
        """
    )
    return int(
        con.execute(f"SELECT COUNT(*) FROM {CORE_TEAM_STATS_WEEKLY_TABLE}").fetchone()[0]
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
        if not {"season", "week", "team_id"}.issubset(tier_b_columns):
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
                    a.team_id AS team_id,
                    a.season AS season,
                    a.week AS week,
                    CAST(a.{field} AS VARCHAR) AS tier_a_value,
                    CAST(TRY_CAST(CAST(b.{field} AS VARCHAR) AS INTEGER) AS VARCHAR)
                        AS tier_b_value
                FROM {CORE_TEAM_STATS_WEEKLY_TABLE} a
                JOIN {spec.stage_qualified_table} b
                  ON UPPER(TRIM(b.team_id)) = a.team_id
                 AND TRY_CAST(b.season AS INTEGER) = a.season
                 AND TRY_CAST(b.week AS INTEGER) = a.week
                WHERE a.{field} IS NOT NULL
                  AND TRY_CAST(CAST(b.{field} AS VARCHAR) AS INTEGER) IS NOT NULL
                  AND a.{field} <> TRY_CAST(CAST(b.{field} AS VARCHAR) AS INTEGER)
                ORDER BY team_id, season, week
                """
            ).fetchall()
            for team_id, season, week, tier_a_value, tier_b_value in rows:
                conflicts.append(
                    ConflictRow(
                        team_id=str(team_id),
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
            scope_type="team_stats_weekly",
            scope_ref=scope_ref,
            reason_code="tier_b_disagreement",
            severity="warning",
            evidence_refs=evidence,
            notes=(
                f"Tier-A ({primary.adapter_id}) vs Tier-B disagreement on "
                f"{len(scope_conflicts)} field(s) for {scope_ref}; Tier-A "
                "value wins in core.team_stats_weekly."
            ),
        )
        case_ids.append(case.quarantine_case_id)
    return case_ids


def execute_core_team_stats_load(
    settings: Settings,
    *,
    execute: bool,
) -> CoreTeamStatsLoadResult:
    primary = primary_slice_for_core_table(CORE_TEAM_STATS_WEEKLY_TABLE)
    if primary is None:
        primary = get_slice("nflverse_bulk", "team_stats_weekly")
    cross_checks = cross_check_slices_for_primary(primary)
    pipeline_name = f"adapter.{primary.adapter_id}.core_load.team_stats_weekly"

    con = duckdb.connect(str(settings.db_path))
    try:
        apply_column_aliases(con, primary.stage_qualified_table, primary.slice_key)
        for spec in cross_checks:
            apply_column_aliases(con, spec.stage_qualified_table, spec.slice_key)
        tier_a_columns = _assert_required_columns(
            con, primary.stage_qualified_table, _REQUIRED_TIER_A_COLUMNS
        )
        source_row_count, distinct_count, invalid_row_count = _profile_tier_a(
            con, primary.stage_qualified_table
        )
        if not execute:
            return CoreTeamStatsLoadResult(
                primary_slice=primary,
                run_mode="dry_run",
                run_status="planned_core_team_stats_load",
                pipeline_name=pipeline_name,
                ingest_run_id="",
                qualified_table=CORE_TEAM_STATS_WEEKLY_TABLE,
                source_row_count=source_row_count,
                row_count=0,
                distinct_team_season_week_count=distinct_count,
                invalid_row_count=invalid_row_count,
                conflict_count=0,
                opened_quarantine_case_ids=(),
                cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
                load_event_id="",
                mart_qualified_table="",
                mart_row_count=0,
                season_mart_qualified_table="",
                season_mart_row_count=0,
            )
        row_count = _rebuild_core_team_stats_weekly(
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
        run_status="core_team_stats_weekly_loaded",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=1,
        message="T2.5E core.team_stats_weekly promotion",
    )
    opened_case_ids = _open_conflict_quarantine(
        settings,
        ingest_run_id=ingest_run_id,
        primary=primary,
        conflicts=conflicts,
    )
    weekly_mart = build_team_stats_weekly_v1(settings)
    season_mart = build_team_stats_season_v1(settings)
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=primary.adapter_id,
        pipeline_name=pipeline_name,
        event_kind="core_loaded",
        target_schema="core",
        target_object="team_stats_weekly",
        row_count=row_count,
        object_path=primary.stage_qualified_table,
        payload={
            "source_table": primary.stage_qualified_table,
            "qualified_table": CORE_TEAM_STATS_WEEKLY_TABLE,
            "source_row_count": source_row_count,
            "distinct_team_season_week_count": distinct_count,
            "invalid_row_count": invalid_row_count,
            "row_count": row_count,
            "conflict_count": len(conflicts),
            "opened_quarantine_case_ids": opened_case_ids,
            "weekly_mart_qualified_table": weekly_mart.qualified_table,
            "weekly_mart_row_count": weekly_mart.row_count,
            "season_mart_qualified_table": season_mart.qualified_table,
            "season_mart_row_count": season_mart.row_count,
        },
    )
    return CoreTeamStatsLoadResult(
        primary_slice=primary,
        run_mode="execute",
        run_status="core_team_stats_weekly_loaded",
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        qualified_table=CORE_TEAM_STATS_WEEKLY_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_team_season_week_count=distinct_count,
        invalid_row_count=invalid_row_count,
        conflict_count=len(conflicts),
        opened_quarantine_case_ids=tuple(opened_case_ids),
        cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
        load_event_id=load_event_id,
        mart_qualified_table=weekly_mart.qualified_table,
        mart_row_count=weekly_mart.row_count,
        season_mart_qualified_table=season_mart.qualified_table,
        season_mart_row_count=season_mart.row_count,
    )


__all__ = [
    "CORE_TEAM_STATS_WEEKLY_TABLE",
    "ConflictRow",
    "CoreTeamStatsLoadResult",
    "execute_core_team_stats_load",
]
