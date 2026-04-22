"""Core promotion for ``core.game`` (T2.5B, ADR-0031).

Reads the Tier-A stage (``stg.nflverse_bulk_games``) as source of truth and
cross-checks every configured Tier-B stage slice (e.g.
``stg.official_context_web_games``) field-by-field. Disagreements open
``meta.quarantine_case`` entries (ADR-0028) with ``scope_type='game'`` and
``reason_code='tier_b_disagreement'``; the Tier-A value always wins in
``core.game`` per ADR-0007. Operator override runs through the existing
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
from new_nfl.mart.game_overview import MART_GAME_OVERVIEW_V1, build_game_overview_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings

CORE_GAME_TABLE = "core.game"

_REQUIRED_TIER_A_COLUMNS: tuple[str, ...] = (
    "game_id",
    "season",
    "week",
    "home_team",
    "away_team",
)

_CANONICAL_COLUMNS: tuple[str, ...] = (
    "game_id",
    "season",
    "game_type",
    "week",
    "gameday",
    "weekday",
    "gametime",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "result",
    "overtime",
    "stadium",
    "roof",
    "surface",
)

# Fields that Tier-B is authoritative *enough* to compare against. Missing
# columns on either side are skipped silently (Tier-B feeds are incomplete
# by design — only what's present is checked). Score drift is the realistic
# conflict during live runs; stadium/roof/surface catch venue-metadata
# inconsistencies that often surface in historical backfills.
_CROSS_CHECK_FIELDS: tuple[str, ...] = (
    "home_score",
    "away_score",
    "stadium",
    "roof",
    "surface",
)


@dataclass(frozen=True)
class ConflictRow:
    game_id: str
    field: str
    tier_a_value: str | None
    tier_b_value: str | None
    tier_b_adapter_id: str


@dataclass(frozen=True)
class CoreGameLoadResult:
    primary_slice: SliceSpec
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_game_count: int
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
            f"{qualified_table} does not exist; run stage-load --slice games first"
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
            f"{qualified_table} is missing required games columns: {', '.join(missing)}"
        )
    return present


def _opt(col: str, present: set[str]) -> str:
    return col if col in present else "NULL"


def _profile_tier_a(
    con: duckdb.DuckDBPyConnection, stage_table: str
) -> tuple[int, int, int]:
    source_row_count = int(con.execute(f"SELECT COUNT(*) FROM {stage_table}").fetchone()[0])
    distinct_game_count = int(
        con.execute(
            f"""
            SELECT COUNT(DISTINCT LOWER(TRIM(game_id)))
            FROM {stage_table}
            WHERE NULLIF(TRIM(game_id), '') IS NOT NULL
            """
        ).fetchone()[0]
    )
    invalid_row_count = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {stage_table}
            WHERE NULLIF(TRIM(game_id), '') IS NULL
               OR NULLIF(TRIM(home_team), '') IS NULL
               OR NULLIF(TRIM(away_team), '') IS NULL
            """
        ).fetchone()[0]
    )
    return source_row_count, distinct_game_count, invalid_row_count


def _rebuild_core_game(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    stage_columns: set[str],
) -> int:
    game_type = _opt("game_type", stage_columns)
    gameday = _opt("gameday", stage_columns)
    weekday = _opt("weekday", stage_columns)
    gametime = _opt("gametime", stage_columns)
    home_score = _opt("home_score", stage_columns)
    away_score = _opt("away_score", stage_columns)
    result_col = _opt("result", stage_columns)
    overtime = _opt("overtime", stage_columns)
    stadium = _opt("stadium", stage_columns)
    roof = _opt("roof", stage_columns)
    surface = _opt("surface", stage_columns)
    loaded_at = "_loaded_at" if "_loaded_at" in stage_columns else "NULL"
    source_file_id = "_source_file_id" if "_source_file_id" in stage_columns else "NULL"
    adapter_id = "_adapter_id" if "_adapter_id" in stage_columns else "NULL"

    con.execute("CREATE SCHEMA IF NOT EXISTS core")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {CORE_GAME_TABLE} AS
        WITH ranked AS (
            SELECT
                LOWER(TRIM(game_id)) AS game_id,
                TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER) AS season,
                NULLIF(TRIM(CAST({game_type} AS VARCHAR)), '') AS game_type,
                TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER) AS week,
                TRY_CAST(NULLIF(TRIM(CAST({gameday} AS VARCHAR)), '') AS DATE) AS gameday,
                NULLIF(TRIM(CAST({weekday} AS VARCHAR)), '') AS weekday,
                NULLIF(TRIM(CAST({gametime} AS VARCHAR)), '') AS gametime,
                UPPER(TRIM(home_team)) AS home_team,
                UPPER(TRIM(away_team)) AS away_team,
                TRY_CAST(NULLIF(TRIM(CAST({home_score} AS VARCHAR)), '') AS INTEGER) AS home_score,
                TRY_CAST(NULLIF(TRIM(CAST({away_score} AS VARCHAR)), '') AS INTEGER) AS away_score,
                TRY_CAST(NULLIF(TRIM(CAST({result_col} AS VARCHAR)), '') AS INTEGER) AS result,
                TRY_CAST(NULLIF(TRIM(CAST({overtime} AS VARCHAR)), '') AS INTEGER) AS overtime,
                NULLIF(TRIM(CAST({stadium} AS VARCHAR)), '') AS stadium,
                NULLIF(TRIM(CAST({roof} AS VARCHAR)), '') AS roof,
                NULLIF(TRIM(CAST({surface} AS VARCHAR)), '') AS surface,
                COALESCE({source_file_id}, '') AS _source_file_id,
                COALESCE({adapter_id}, '') AS _adapter_id,
                {loaded_at} AS _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY LOWER(TRIM(game_id))
                    ORDER BY {loaded_at} DESC NULLS LAST, {source_file_id} DESC
                ) AS _rn
            FROM {stage_table}
            WHERE NULLIF(TRIM(game_id), '') IS NOT NULL
              AND NULLIF(TRIM(home_team), '') IS NOT NULL
              AND NULLIF(TRIM(away_team), '') IS NOT NULL
        )
        SELECT
            game_id,
            season,
            game_type,
            week,
            gameday,
            weekday,
            gametime,
            home_team,
            away_team,
            home_score,
            away_score,
            result,
            overtime,
            stadium,
            roof,
            surface,
            _source_file_id,
            _adapter_id,
            CURRENT_TIMESTAMP AS _canonicalized_at
        FROM ranked
        WHERE _rn = 1
        """
    )
    return int(con.execute(f"SELECT COUNT(*) FROM {CORE_GAME_TABLE}").fetchone()[0])


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
        if "game_id" not in tier_b_columns:
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
                    LOWER(TRIM(a.game_id)) AS game_id,
                    NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') AS tier_a_value,
                    NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') AS tier_b_value
                FROM {CORE_GAME_TABLE} a
                JOIN {spec.stage_qualified_table} b
                  ON LOWER(TRIM(a.game_id)) = LOWER(TRIM(b.game_id))
                WHERE NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') IS NOT NULL
                  AND NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') IS NOT NULL
                  AND LOWER(TRIM(CAST(a.{field} AS VARCHAR)))
                      <> LOWER(TRIM(CAST(b.{field} AS VARCHAR)))
                ORDER BY game_id
                """
            ).fetchall()
            for game_id, tier_a_value, tier_b_value in rows:
                conflicts.append(
                    ConflictRow(
                        game_id=str(game_id),
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
    by_game: dict[str, list[ConflictRow]] = {}
    for c in conflicts:
        by_game.setdefault(c.game_id, []).append(c)
    case_ids: list[str] = []
    for game_id, game_conflicts in sorted(by_game.items()):
        evidence = [
            {
                "field": c.field,
                "tier_a_value": c.tier_a_value,
                "tier_b_value": c.tier_b_value,
                "tier_b_adapter_id": c.tier_b_adapter_id,
                "tier_a_adapter_id": primary.adapter_id,
                "ingest_run_id": ingest_run_id,
            }
            for c in game_conflicts
        ]
        case = open_quarantine_case(
            settings,
            scope_type="game",
            scope_ref=game_id,
            reason_code="tier_b_disagreement",
            severity="warning",
            evidence_refs=evidence,
            notes=(
                f"Tier-A ({primary.adapter_id}) vs Tier-B disagreement on "
                f"{len(game_conflicts)} field(s); Tier-A value wins in core.game."
            ),
        )
        case_ids.append(case.quarantine_case_id)
    return case_ids


def execute_core_game_load(
    settings: Settings,
    *,
    execute: bool,
) -> CoreGameLoadResult:
    primary = primary_slice_for_core_table(CORE_GAME_TABLE)
    if primary is None:
        # Defensive: registry must declare a primary for core.game.
        primary = get_slice("nflverse_bulk", "games")
    cross_checks = cross_check_slices_for_primary(primary)
    pipeline_name = f"adapter.{primary.adapter_id}.core_load.games"

    con = duckdb.connect(str(settings.db_path))
    try:
        tier_a_columns = _assert_required_columns(
            con, primary.stage_qualified_table, _REQUIRED_TIER_A_COLUMNS
        )
        source_row_count, distinct_game_count, invalid_row_count = _profile_tier_a(
            con, primary.stage_qualified_table
        )
        if not execute:
            return CoreGameLoadResult(
                primary_slice=primary,
                run_mode="dry_run",
                run_status="planned_core_game_load",
                pipeline_name=pipeline_name,
                ingest_run_id="",
                qualified_table=CORE_GAME_TABLE,
                source_row_count=source_row_count,
                row_count=0,
                distinct_game_count=distinct_game_count,
                invalid_row_count=invalid_row_count,
                conflict_count=0,
                opened_quarantine_case_ids=(),
                cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
                load_event_id="",
                mart_qualified_table="",
                mart_row_count=0,
            )
        row_count = _rebuild_core_game(con, primary.stage_qualified_table, tier_a_columns)
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
        run_status="core_game_loaded",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=1,
        message="T2.5B core.game promotion",
    )
    opened_case_ids = _open_conflict_quarantine(
        settings,
        ingest_run_id=ingest_run_id,
        primary=primary,
        conflicts=conflicts,
    )
    mart_result = build_game_overview_v1(settings)
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=primary.adapter_id,
        pipeline_name=pipeline_name,
        event_kind="core_loaded",
        target_schema="core",
        target_object="game",
        row_count=row_count,
        object_path=primary.stage_qualified_table,
        payload={
            "source_table": primary.stage_qualified_table,
            "qualified_table": CORE_GAME_TABLE,
            "source_row_count": source_row_count,
            "distinct_game_count": distinct_game_count,
            "invalid_row_count": invalid_row_count,
            "row_count": row_count,
            "conflict_count": len(conflicts),
            "opened_quarantine_case_ids": opened_case_ids,
            "mart_qualified_table": mart_result.qualified_table,
            "mart_row_count": mart_result.row_count,
        },
    )
    return CoreGameLoadResult(
        primary_slice=primary,
        run_mode="execute",
        run_status="core_game_loaded",
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        qualified_table=CORE_GAME_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_game_count=distinct_game_count,
        invalid_row_count=invalid_row_count,
        conflict_count=len(conflicts),
        opened_quarantine_case_ids=tuple(opened_case_ids),
        cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
        load_event_id=load_event_id,
        mart_qualified_table=mart_result.qualified_table,
        mart_row_count=mart_result.row_count,
    )


__all__ = [
    "CORE_GAME_TABLE",
    "ConflictRow",
    "CoreGameLoadResult",
    "execute_core_game_load",
]
