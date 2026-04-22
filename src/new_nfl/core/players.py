"""Core promotion for ``core.player`` (T2.5C, ADR-0031).

Reads the Tier-A stage (``stg.nflverse_bulk_players``) as source of truth and
cross-checks every configured Tier-B stage slice (e.g.
``stg.official_context_web_players``) field-by-field. Disagreements open
``meta.quarantine_case`` entries (ADR-0028) with ``scope_type='player'`` and
``reason_code='tier_b_disagreement'``; the Tier-A value always wins in
``core.player`` per ADR-0007. Operator override runs through the existing
``resolve_quarantine_case`` pipeline.

Identical shape and dispatch pattern as :mod:`new_nfl.core.teams` and
:mod:`new_nfl.core.games`; differences are the primary-key canonicalization
(``UPPER(TRIM(player_id))``), the richer player-specific column set and the
downstream dedupe-integration hook (see :mod:`new_nfl.core.player_records`).
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
from new_nfl.mart.player_overview import build_player_overview_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings

CORE_PLAYER_TABLE = "core.player"

_REQUIRED_TIER_A_COLUMNS: tuple[str, ...] = (
    "player_id",
    "display_name",
)

_CANONICAL_COLUMNS: tuple[str, ...] = (
    "player_id",
    "display_name",
    "first_name",
    "last_name",
    "birth_date",
    "position",
    "height",
    "weight",
    "college_name",
    "rookie_season",
    "last_season",
    "current_team_id",
    "jersey_number",
    "draft_club",
    "draft_year",
    "draft_round",
    "draft_pick",
    "status",
)

# Fields that Tier-B is authoritative *enough* to compare against. Missing
# columns on either side are skipped silently (Tier-B feeds are incomplete
# by design — only what's present is checked). Name / position / team drift
# is the realistic conflict signal during live runs; jersey_number catches
# mid-season transactions that Tier-A may lag on.
_CROSS_CHECK_FIELDS: tuple[str, ...] = (
    "display_name",
    "position",
    "current_team_id",
    "jersey_number",
)


@dataclass(frozen=True)
class ConflictRow:
    player_id: str
    field: str
    tier_a_value: str | None
    tier_b_value: str | None
    tier_b_adapter_id: str


@dataclass(frozen=True)
class CorePlayerLoadResult:
    primary_slice: SliceSpec
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_player_count: int
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
            f"{qualified_table} does not exist; run stage-load --slice players first"
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
            f"{qualified_table} is missing required players columns: {', '.join(missing)}"
        )
    return present


def _opt(col: str, present: set[str]) -> str:
    return col if col in present else "NULL"


def _profile_tier_a(
    con: duckdb.DuckDBPyConnection, stage_table: str
) -> tuple[int, int, int]:
    source_row_count = int(con.execute(f"SELECT COUNT(*) FROM {stage_table}").fetchone()[0])
    distinct_player_count = int(
        con.execute(
            f"""
            SELECT COUNT(DISTINCT UPPER(TRIM(player_id)))
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
            """
        ).fetchone()[0]
    )
    invalid_row_count = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NULL
               OR NULLIF(TRIM(display_name), '') IS NULL
            """
        ).fetchone()[0]
    )
    return source_row_count, distinct_player_count, invalid_row_count


def _rebuild_core_player(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    stage_columns: set[str],
) -> int:
    first_name = _opt("first_name", stage_columns)
    last_name = _opt("last_name", stage_columns)
    birth_date = _opt("birth_date", stage_columns)
    position = _opt("position", stage_columns)
    height = _opt("height", stage_columns)
    weight = _opt("weight", stage_columns)
    college_name = _opt("college_name", stage_columns)
    rookie_season = _opt("rookie_season", stage_columns)
    last_season = _opt("last_season", stage_columns)
    current_team_id = _opt("current_team_id", stage_columns)
    jersey_number = _opt("jersey_number", stage_columns)
    draft_club = _opt("draft_club", stage_columns)
    draft_year = _opt("draft_year", stage_columns)
    draft_round = _opt("draft_round", stage_columns)
    draft_pick = _opt("draft_pick", stage_columns)
    status = _opt("status", stage_columns)
    loaded_at = "_loaded_at" if "_loaded_at" in stage_columns else "NULL"
    source_file_id = "_source_file_id" if "_source_file_id" in stage_columns else "NULL"
    adapter_id = "_adapter_id" if "_adapter_id" in stage_columns else "NULL"

    con.execute("CREATE SCHEMA IF NOT EXISTS core")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {CORE_PLAYER_TABLE} AS
        WITH ranked AS (
            SELECT
                UPPER(TRIM(player_id)) AS player_id,
                NULLIF(TRIM(display_name), '') AS display_name,
                NULLIF(TRIM(CAST({first_name} AS VARCHAR)), '') AS first_name,
                NULLIF(TRIM(CAST({last_name} AS VARCHAR)), '') AS last_name,
                TRY_CAST(NULLIF(TRIM(CAST({birth_date} AS VARCHAR)), '') AS DATE) AS birth_date,
                UPPER(NULLIF(TRIM(CAST({position} AS VARCHAR)), '')) AS position,
                TRY_CAST(NULLIF(TRIM(CAST({height} AS VARCHAR)), '') AS INTEGER) AS height,
                TRY_CAST(NULLIF(TRIM(CAST({weight} AS VARCHAR)), '') AS INTEGER) AS weight,
                NULLIF(TRIM(CAST({college_name} AS VARCHAR)), '') AS college_name,
                TRY_CAST(NULLIF(TRIM(CAST({rookie_season} AS VARCHAR)), '') AS INTEGER) AS rookie_season,
                TRY_CAST(NULLIF(TRIM(CAST({last_season} AS VARCHAR)), '') AS INTEGER) AS last_season,
                UPPER(NULLIF(TRIM(CAST({current_team_id} AS VARCHAR)), '')) AS current_team_id,
                TRY_CAST(NULLIF(TRIM(CAST({jersey_number} AS VARCHAR)), '') AS INTEGER) AS jersey_number,
                UPPER(NULLIF(TRIM(CAST({draft_club} AS VARCHAR)), '')) AS draft_club,
                TRY_CAST(NULLIF(TRIM(CAST({draft_year} AS VARCHAR)), '') AS INTEGER) AS draft_year,
                TRY_CAST(NULLIF(TRIM(CAST({draft_round} AS VARCHAR)), '') AS INTEGER) AS draft_round,
                TRY_CAST(NULLIF(TRIM(CAST({draft_pick} AS VARCHAR)), '') AS INTEGER) AS draft_pick,
                NULLIF(TRIM(CAST({status} AS VARCHAR)), '') AS status,
                COALESCE({source_file_id}, '') AS _source_file_id,
                COALESCE({adapter_id}, '') AS _adapter_id,
                {loaded_at} AS _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(TRIM(player_id))
                    ORDER BY {loaded_at} DESC NULLS LAST, {source_file_id} DESC
                ) AS _rn
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
              AND NULLIF(TRIM(display_name), '') IS NOT NULL
        )
        SELECT
            player_id,
            display_name,
            first_name,
            last_name,
            birth_date,
            position,
            height,
            weight,
            college_name,
            rookie_season,
            last_season,
            current_team_id,
            jersey_number,
            draft_club,
            draft_year,
            draft_round,
            draft_pick,
            status,
            _source_file_id,
            _adapter_id,
            CURRENT_TIMESTAMP AS _canonicalized_at
        FROM ranked
        WHERE _rn = 1
        """
    )
    return int(con.execute(f"SELECT COUNT(*) FROM {CORE_PLAYER_TABLE}").fetchone()[0])


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
        if "player_id" not in tier_b_columns:
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
                    UPPER(TRIM(a.player_id)) AS player_id,
                    NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') AS tier_a_value,
                    NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') AS tier_b_value
                FROM {CORE_PLAYER_TABLE} a
                JOIN {spec.stage_qualified_table} b
                  ON UPPER(TRIM(a.player_id)) = UPPER(TRIM(b.player_id))
                WHERE NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') IS NOT NULL
                  AND NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') IS NOT NULL
                  AND LOWER(TRIM(CAST(a.{field} AS VARCHAR)))
                      <> LOWER(TRIM(CAST(b.{field} AS VARCHAR)))
                ORDER BY player_id
                """
            ).fetchall()
            for player_id, tier_a_value, tier_b_value in rows:
                conflicts.append(
                    ConflictRow(
                        player_id=str(player_id),
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
    by_player: dict[str, list[ConflictRow]] = {}
    for c in conflicts:
        by_player.setdefault(c.player_id, []).append(c)
    case_ids: list[str] = []
    for player_id, player_conflicts in sorted(by_player.items()):
        evidence = [
            {
                "field": c.field,
                "tier_a_value": c.tier_a_value,
                "tier_b_value": c.tier_b_value,
                "tier_b_adapter_id": c.tier_b_adapter_id,
                "tier_a_adapter_id": primary.adapter_id,
                "ingest_run_id": ingest_run_id,
            }
            for c in player_conflicts
        ]
        case = open_quarantine_case(
            settings,
            scope_type="player",
            scope_ref=player_id,
            reason_code="tier_b_disagreement",
            severity="warning",
            evidence_refs=evidence,
            notes=(
                f"Tier-A ({primary.adapter_id}) vs Tier-B disagreement on "
                f"{len(player_conflicts)} field(s); Tier-A value wins in core.player."
            ),
        )
        case_ids.append(case.quarantine_case_id)
    return case_ids


def execute_core_player_load(
    settings: Settings,
    *,
    execute: bool,
) -> CorePlayerLoadResult:
    primary = primary_slice_for_core_table(CORE_PLAYER_TABLE)
    if primary is None:
        # Defensive: registry must declare a primary for core.player.
        primary = get_slice("nflverse_bulk", "players")
    cross_checks = cross_check_slices_for_primary(primary)
    pipeline_name = f"adapter.{primary.adapter_id}.core_load.players"

    con = duckdb.connect(str(settings.db_path))
    try:
        tier_a_columns = _assert_required_columns(
            con, primary.stage_qualified_table, _REQUIRED_TIER_A_COLUMNS
        )
        source_row_count, distinct_player_count, invalid_row_count = _profile_tier_a(
            con, primary.stage_qualified_table
        )
        if not execute:
            return CorePlayerLoadResult(
                primary_slice=primary,
                run_mode="dry_run",
                run_status="planned_core_player_load",
                pipeline_name=pipeline_name,
                ingest_run_id="",
                qualified_table=CORE_PLAYER_TABLE,
                source_row_count=source_row_count,
                row_count=0,
                distinct_player_count=distinct_player_count,
                invalid_row_count=invalid_row_count,
                conflict_count=0,
                opened_quarantine_case_ids=(),
                cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
                load_event_id="",
                mart_qualified_table="",
                mart_row_count=0,
            )
        row_count = _rebuild_core_player(con, primary.stage_qualified_table, tier_a_columns)
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
        run_status="core_player_loaded",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=1,
        message="T2.5C core.player promotion",
    )
    opened_case_ids = _open_conflict_quarantine(
        settings,
        ingest_run_id=ingest_run_id,
        primary=primary,
        conflicts=conflicts,
    )
    mart_result = build_player_overview_v1(settings)
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=primary.adapter_id,
        pipeline_name=pipeline_name,
        event_kind="core_loaded",
        target_schema="core",
        target_object="player",
        row_count=row_count,
        object_path=primary.stage_qualified_table,
        payload={
            "source_table": primary.stage_qualified_table,
            "qualified_table": CORE_PLAYER_TABLE,
            "source_row_count": source_row_count,
            "distinct_player_count": distinct_player_count,
            "invalid_row_count": invalid_row_count,
            "row_count": row_count,
            "conflict_count": len(conflicts),
            "opened_quarantine_case_ids": opened_case_ids,
            "mart_qualified_table": mart_result.qualified_table,
            "mart_row_count": mart_result.row_count,
        },
    )
    return CorePlayerLoadResult(
        primary_slice=primary,
        run_mode="execute",
        run_status="core_player_loaded",
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        qualified_table=CORE_PLAYER_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_player_count=distinct_player_count,
        invalid_row_count=invalid_row_count,
        conflict_count=len(conflicts),
        opened_quarantine_case_ids=tuple(opened_case_ids),
        cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
        load_event_id=load_event_id,
        mart_qualified_table=mart_result.qualified_table,
        mart_row_count=mart_result.row_count,
    )


__all__ = [
    "CORE_PLAYER_TABLE",
    "ConflictRow",
    "CorePlayerLoadResult",
    "execute_core_player_load",
]
