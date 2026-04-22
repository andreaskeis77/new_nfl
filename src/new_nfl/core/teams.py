"""Core promotion for ``core.team`` (T2.5A, ADR-0031).

Reads the Tier-A stage (``stg.nflverse_bulk_teams``) as source of truth and
cross-checks every configured Tier-B stage slice (e.g.
``stg.official_context_web_teams``) field-by-field. Disagreements open
``meta.quarantine_case`` entries (ADR-0028) with ``scope_type='team'`` and
``reason_code='tier_b_disagreement'``; the Tier-A value always wins in
``core.team`` per ADR-0007. Operator override runs through the existing
``resolve_quarantine_case`` pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import duckdb

from new_nfl.adapters.slices import (
    SliceSpec,
    cross_check_slices_for_primary,
    get_slice,
    primary_slice_for_core_table,
)
from new_nfl.jobs.quarantine import open_quarantine_case
from new_nfl.mart.team_overview import MART_TEAM_OVERVIEW_V1, build_team_overview_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings

CORE_TEAM_TABLE = "core.team"

_REQUIRED_TIER_A_COLUMNS: tuple[str, ...] = (
    "team_id",
    "team_abbr",
    "team_name",
)

_CANONICAL_COLUMNS: tuple[str, ...] = (
    "team_id",
    "team_abbr",
    "team_name",
    "team_nick",
    "team_conference",
    "team_division",
    "team_color",
    "team_color2",
    "first_season",
    "last_season",
    "successor_team_id",
)

# Fields that Tier-B is authoritative *enough* to compare against. Missing
# columns on either side are skipped silently (Tier-B feeds are incomplete
# by design — only what's present is checked).
_CROSS_CHECK_FIELDS: tuple[str, ...] = (
    "team_abbr",
    "team_name",
    "team_conference",
    "team_division",
    "team_color",
)


@dataclass(frozen=True)
class ConflictRow:
    team_id: str
    field: str
    tier_a_value: str | None
    tier_b_value: str | None
    tier_b_adapter_id: str


@dataclass(frozen=True)
class CoreTeamLoadResult:
    primary_slice: SliceSpec
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_team_count: int
    invalid_row_count: int
    conflict_count: int
    opened_quarantine_case_ids: tuple[str, ...]
    cross_check_slice_keys: tuple[str, ...]
    load_event_id: str
    mart_qualified_table: str
    mart_row_count: int


def _describe_columns(con: duckdb.DuckDBPyConnection, qualified_table: str) -> set[str]:
    try:
        rows = con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f"{qualified_table} does not exist; run stage-load --slice teams first"
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
            f"{qualified_table} is missing required teams columns: {', '.join(missing)}"
        )
    return present


def _opt(col: str, present: set[str]) -> str:
    return col if col in present else "NULL"


def _profile_tier_a(
    con: duckdb.DuckDBPyConnection, stage_table: str
) -> tuple[int, int, int]:
    source_row_count = int(con.execute(f"SELECT COUNT(*) FROM {stage_table}").fetchone()[0])
    distinct_team_count = int(
        con.execute(
            f"""
            SELECT COUNT(DISTINCT UPPER(TRIM(team_id)))
            FROM {stage_table}
            WHERE NULLIF(TRIM(team_id), '') IS NOT NULL
            """
        ).fetchone()[0]
    )
    invalid_row_count = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {stage_table}
            WHERE NULLIF(TRIM(team_id), '') IS NULL
            """
        ).fetchone()[0]
    )
    return source_row_count, distinct_team_count, invalid_row_count


def _rebuild_core_team(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    stage_columns: set[str],
) -> int:
    team_nick = _opt("team_nick", stage_columns)
    team_conference = _opt("team_conference", stage_columns)
    team_division = _opt("team_division", stage_columns)
    team_color = _opt("team_color", stage_columns)
    team_color2 = _opt("team_color2", stage_columns)
    first_season = _opt("first_season", stage_columns)
    last_season = _opt("last_season", stage_columns)
    successor_team_id = _opt("successor_team_id", stage_columns)
    loaded_at = "_loaded_at" if "_loaded_at" in stage_columns else "NULL"
    source_file_id = "_source_file_id" if "_source_file_id" in stage_columns else "NULL"
    adapter_id = "_adapter_id" if "_adapter_id" in stage_columns else "NULL"

    con.execute("CREATE SCHEMA IF NOT EXISTS core")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {CORE_TEAM_TABLE} AS
        WITH ranked AS (
            SELECT
                UPPER(TRIM(team_id)) AS team_id,
                NULLIF(TRIM(team_abbr), '') AS team_abbr,
                NULLIF(TRIM(team_name), '') AS team_name,
                NULLIF(TRIM(CAST({team_nick} AS VARCHAR)), '') AS team_nick,
                NULLIF(TRIM(CAST({team_conference} AS VARCHAR)), '') AS team_conference,
                NULLIF(TRIM(CAST({team_division} AS VARCHAR)), '') AS team_division,
                NULLIF(TRIM(CAST({team_color} AS VARCHAR)), '') AS team_color,
                NULLIF(TRIM(CAST({team_color2} AS VARCHAR)), '') AS team_color2,
                TRY_CAST(NULLIF(TRIM(CAST({first_season} AS VARCHAR)), '') AS INTEGER) AS first_season,
                TRY_CAST(NULLIF(TRIM(CAST({last_season} AS VARCHAR)), '') AS INTEGER) AS last_season,
                NULLIF(TRIM(CAST({successor_team_id} AS VARCHAR)), '') AS successor_team_id,
                COALESCE({source_file_id}, '') AS _source_file_id,
                COALESCE({adapter_id}, '') AS _adapter_id,
                {loaded_at} AS _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(TRIM(team_id))
                    ORDER BY {loaded_at} DESC NULLS LAST, {source_file_id} DESC
                ) AS _rn
            FROM {stage_table}
            WHERE NULLIF(TRIM(team_id), '') IS NOT NULL
        )
        SELECT
            team_id,
            team_abbr,
            team_name,
            team_nick,
            team_conference,
            team_division,
            team_color,
            team_color2,
            first_season,
            last_season,
            successor_team_id,
            _source_file_id,
            _adapter_id,
            CURRENT_TIMESTAMP AS _canonicalized_at
        FROM ranked
        WHERE _rn = 1
        """
    )
    return int(con.execute(f"SELECT COUNT(*) FROM {CORE_TEAM_TABLE}").fetchone()[0])


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
            # Cross-check stage not yet loaded — skip silently.
            continue
        if "team_id" not in tier_b_columns:
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
                    UPPER(TRIM(a.team_id)) AS team_id,
                    NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') AS tier_a_value,
                    NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') AS tier_b_value
                FROM {CORE_TEAM_TABLE} a
                JOIN {spec.stage_qualified_table} b
                  ON UPPER(TRIM(a.team_id)) = UPPER(TRIM(b.team_id))
                WHERE NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') IS NOT NULL
                  AND NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') IS NOT NULL
                  AND LOWER(TRIM(CAST(a.{field} AS VARCHAR)))
                      <> LOWER(TRIM(CAST(b.{field} AS VARCHAR)))
                ORDER BY team_id
                """
            ).fetchall()
            for team_id, tier_a_value, tier_b_value in rows:
                conflicts.append(
                    ConflictRow(
                        team_id=str(team_id),
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
    by_team: dict[str, list[ConflictRow]] = {}
    for c in conflicts:
        by_team.setdefault(c.team_id, []).append(c)
    case_ids: list[str] = []
    for team_id, team_conflicts in sorted(by_team.items()):
        evidence = [
            {
                "field": c.field,
                "tier_a_value": c.tier_a_value,
                "tier_b_value": c.tier_b_value,
                "tier_b_adapter_id": c.tier_b_adapter_id,
                "tier_a_adapter_id": primary.adapter_id,
                "ingest_run_id": ingest_run_id,
            }
            for c in team_conflicts
        ]
        case = open_quarantine_case(
            settings,
            scope_type="team",
            scope_ref=team_id,
            reason_code="tier_b_disagreement",
            severity="warning",
            evidence_refs=evidence,
            notes=(
                f"Tier-A ({primary.adapter_id}) vs Tier-B disagreement on "
                f"{len(team_conflicts)} field(s); Tier-A value wins in core.team."
            ),
        )
        case_ids.append(case.quarantine_case_id)
    return case_ids


def execute_core_team_load(
    settings: Settings,
    *,
    execute: bool,
) -> CoreTeamLoadResult:
    primary = primary_slice_for_core_table(CORE_TEAM_TABLE)
    if primary is None:
        # Defensive: registry must declare a primary for core.team.
        primary = get_slice("nflverse_bulk", "teams")
    cross_checks = cross_check_slices_for_primary(primary)
    pipeline_name = f"adapter.{primary.adapter_id}.core_load.teams"

    con = duckdb.connect(str(settings.db_path))
    try:
        tier_a_columns = _assert_required_columns(
            con, primary.stage_qualified_table, _REQUIRED_TIER_A_COLUMNS
        )
        source_row_count, distinct_team_count, invalid_row_count = _profile_tier_a(
            con, primary.stage_qualified_table
        )
        if not execute:
            return CoreTeamLoadResult(
                primary_slice=primary,
                run_mode="dry_run",
                run_status="planned_core_team_load",
                pipeline_name=pipeline_name,
                ingest_run_id="",
                qualified_table=CORE_TEAM_TABLE,
                source_row_count=source_row_count,
                row_count=0,
                distinct_team_count=distinct_team_count,
                invalid_row_count=invalid_row_count,
                conflict_count=0,
                opened_quarantine_case_ids=(),
                cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
                load_event_id="",
                mart_qualified_table="",
                mart_row_count=0,
            )
        row_count = _rebuild_core_team(con, primary.stage_qualified_table, tier_a_columns)
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
        run_status="core_team_loaded",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=1,
        message="T2.5A core.team promotion",
    )
    opened_case_ids = _open_conflict_quarantine(
        settings,
        ingest_run_id=ingest_run_id,
        primary=primary,
        conflicts=conflicts,
    )
    mart_result = build_team_overview_v1(settings)
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=primary.adapter_id,
        pipeline_name=pipeline_name,
        event_kind="core_loaded",
        target_schema="core",
        target_object="team",
        row_count=row_count,
        object_path=primary.stage_qualified_table,
        payload={
            "source_table": primary.stage_qualified_table,
            "qualified_table": CORE_TEAM_TABLE,
            "source_row_count": source_row_count,
            "distinct_team_count": distinct_team_count,
            "invalid_row_count": invalid_row_count,
            "row_count": row_count,
            "conflict_count": len(conflicts),
            "opened_quarantine_case_ids": opened_case_ids,
            "mart_qualified_table": mart_result.qualified_table,
            "mart_row_count": mart_result.row_count,
        },
    )
    return CoreTeamLoadResult(
        primary_slice=primary,
        run_mode="execute",
        run_status="core_team_loaded",
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        qualified_table=CORE_TEAM_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_team_count=distinct_team_count,
        invalid_row_count=invalid_row_count,
        conflict_count=len(conflicts),
        opened_quarantine_case_ids=tuple(opened_case_ids),
        cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
        load_event_id=load_event_id,
        mart_qualified_table=mart_result.qualified_table,
        mart_row_count=mart_result.row_count,
    )


__all__ = [
    "CORE_TEAM_TABLE",
    "ConflictRow",
    "CoreTeamLoadResult",
    "execute_core_team_load",
]
