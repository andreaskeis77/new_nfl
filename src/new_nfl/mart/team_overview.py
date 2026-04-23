"""Mart builder for ``mart.team_overview_v1`` (T2.5A, ADR-0029 + ADR-0031).

Denormalized read projection of ``core.team``. Full rebuild via
``CREATE OR REPLACE TABLE``. Adds pre-lowercased filter columns, the
``is_active`` flag (derived from ``last_season``) and build provenance.
UI/API read exclusively from this projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.meta import schema_cache
from new_nfl.settings import Settings

MART_TEAM_OVERVIEW_V1 = "mart.team_overview_v1"
_SOURCE_TABLE = "core.team"


@dataclass(frozen=True)
class MartTeamOverviewResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    built_at: datetime


def _source_columns(
    settings: Settings, con: duckdb.DuckDBPyConnection
) -> set[str]:
    try:
        rows = schema_cache.describe(settings, _SOURCE_TABLE, con=con)
    except duckdb.Error as exc:
        raise ValueError(
            f"{_SOURCE_TABLE} does not exist; run core-load --slice teams "
            "--execute first"
        ) from exc
    return {str(r[0]).strip().lower() for r in rows}


def _opt(name: str, present: set[str]) -> str:
    return name if name in present else "NULL"


@register_mart_builder("team_overview_v1")
def build_team_overview_v1(settings: Settings) -> MartTeamOverviewResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _source_columns(settings, con)
        required = {"team_id", "team_abbr", "team_name"}
        missing = sorted(required - cols)
        if missing:
            raise ValueError(
                f"{_SOURCE_TABLE} is missing required columns: {', '.join(missing)}"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        team_nick = _opt("team_nick", cols)
        team_conference = _opt("team_conference", cols)
        team_division = _opt("team_division", cols)
        team_color = _opt("team_color", cols)
        team_color2 = _opt("team_color2", cols)
        first_season = _opt("first_season", cols)
        last_season = _opt("last_season", cols)
        successor_team_id = _opt("successor_team_id", cols)
        source_file_id = _opt("_source_file_id", cols)
        adapter_id = _opt("_adapter_id", cols)
        canonicalized_at = _opt("_canonicalized_at", cols)

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_TEAM_OVERVIEW_V1} AS
            SELECT
                team_id,
                team_abbr,
                team_name,
                {team_nick} AS team_nick,
                {team_conference} AS team_conference,
                {team_division} AS team_division,
                {team_color} AS team_color,
                {team_color2} AS team_color2,
                {first_season} AS first_season,
                {last_season} AS last_season,
                {successor_team_id} AS successor_team_id,
                LOWER(team_id) AS team_id_lower,
                LOWER(COALESCE(team_abbr, '')) AS team_abbr_lower,
                LOWER(COALESCE(team_name, '')) AS team_name_lower,
                CASE WHEN {last_season} IS NULL THEN TRUE ELSE FALSE END AS is_active,
                {source_file_id} AS source_file_id,
                {adapter_id} AS source_adapter_id,
                {canonicalized_at} AS source_canonicalized_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE}
            """
        )
        row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {MART_TEAM_OVERVIEW_V1}").fetchone()[0]
        )
    finally:
        con.close()
    built_at = datetime.now()
    return MartTeamOverviewResult(
        qualified_table=MART_TEAM_OVERVIEW_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=built_at,
    )


__all__ = [
    "MART_TEAM_OVERVIEW_V1",
    "MartTeamOverviewResult",
    "build_team_overview_v1",
]
