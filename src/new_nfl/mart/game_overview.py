"""Mart builder for ``mart.game_overview_v1`` (T2.5B, ADR-0029 + ADR-0031).

Denormalized read projection of ``core.game``. Full rebuild via
``CREATE OR REPLACE TABLE``. Adds pre-lowercased filter columns, the
``is_completed`` flag (both scores present), the ``winner_team`` derivation
and build provenance. UI/API read exclusively from this projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.settings import Settings

MART_GAME_OVERVIEW_V1 = "mart.game_overview_v1"
_SOURCE_TABLE = "core.game"


@dataclass(frozen=True)
class MartGameOverviewResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    built_at: datetime


def _source_columns(con: duckdb.DuckDBPyConnection) -> set[str]:
    try:
        rows = con.execute(f"DESCRIBE {_SOURCE_TABLE}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f"{_SOURCE_TABLE} does not exist; run core-load --slice games "
            "--execute first"
        ) from exc
    return {str(r[0]).strip().lower() for r in rows}


def _opt(name: str, present: set[str]) -> str:
    return name if name in present else "NULL"


@register_mart_builder("game_overview_v1")
def build_game_overview_v1(settings: Settings) -> MartGameOverviewResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _source_columns(con)
        required = {"game_id", "season", "week", "home_team", "away_team"}
        missing = sorted(required - cols)
        if missing:
            raise ValueError(
                f"{_SOURCE_TABLE} is missing required columns: {', '.join(missing)}"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        game_type = _opt("game_type", cols)
        gameday = _opt("gameday", cols)
        weekday = _opt("weekday", cols)
        gametime = _opt("gametime", cols)
        home_score = _opt("home_score", cols)
        away_score = _opt("away_score", cols)
        result_col = _opt("result", cols)
        overtime = _opt("overtime", cols)
        stadium = _opt("stadium", cols)
        roof = _opt("roof", cols)
        surface = _opt("surface", cols)
        source_file_id = _opt("_source_file_id", cols)
        adapter_id = _opt("_adapter_id", cols)
        canonicalized_at = _opt("_canonicalized_at", cols)

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_GAME_OVERVIEW_V1} AS
            SELECT
                game_id,
                season,
                {game_type} AS game_type,
                week,
                {gameday} AS gameday,
                {weekday} AS weekday,
                {gametime} AS gametime,
                home_team,
                away_team,
                {home_score} AS home_score,
                {away_score} AS away_score,
                {result_col} AS result,
                {overtime} AS overtime,
                {stadium} AS stadium,
                {roof} AS roof,
                {surface} AS surface,
                LOWER(game_id) AS game_id_lower,
                LOWER(COALESCE(home_team, '')) AS home_team_lower,
                LOWER(COALESCE(away_team, '')) AS away_team_lower,
                CASE
                    WHEN {home_score} IS NOT NULL AND {away_score} IS NOT NULL THEN TRUE
                    ELSE FALSE
                END AS is_completed,
                CASE
                    WHEN {home_score} IS NULL OR {away_score} IS NULL THEN NULL
                    WHEN {home_score} > {away_score} THEN home_team
                    WHEN {away_score} > {home_score} THEN away_team
                    ELSE 'TIE'
                END AS winner_team,
                {source_file_id} AS source_file_id,
                {adapter_id} AS source_adapter_id,
                {canonicalized_at} AS source_canonicalized_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE}
            """
        )
        row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {MART_GAME_OVERVIEW_V1}").fetchone()[0]
        )
    finally:
        con.close()
    built_at = datetime.now()
    return MartGameOverviewResult(
        qualified_table=MART_GAME_OVERVIEW_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=built_at,
    )


__all__ = [
    "MART_GAME_OVERVIEW_V1",
    "MartGameOverviewResult",
    "build_game_overview_v1",
]
