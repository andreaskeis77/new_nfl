"""Mart builder for ``mart.player_stats_weekly_v1`` (T2.5F, ADR-0029 + ADR-0031).

Read projection of ``core.player_stats_weekly`` at the original
``(season, week, player_id)`` grain. Adds derived ``total_yards`` and
``total_touchdowns`` columns plus best-effort LEFT JOIN on ``core.player`` and
``core.team`` for ``display_name``/``team_name``/``team_abbr`` (NULL when the
adjacent core tables have not been loaded). UI/API read exclusively from
this projection.

Note: aggregates assume the Tier-A upstream already filters to regular-season
rows. For playoff separation we will need a ``week <= 18`` filter or a
``season_type`` join in T2.6 when the first UI Career view lands.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.settings import Settings

MART_PLAYER_STATS_WEEKLY_V1 = "mart.player_stats_weekly_v1"
_SOURCE_TABLE = "core.player_stats_weekly"
_PLAYER_TABLE = "core.player"
_TEAM_TABLE = "core.team"


@dataclass(frozen=True)
class MartPlayerStatsWeeklyResult:
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
            f"{_SOURCE_TABLE} does not exist; run core-load --slice "
            "player_stats_weekly --execute first"
        ) from exc
    return {str(r[0]).strip().lower() for r in rows}


def _has_table(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return False
    return True


@register_mart_builder("player_stats_weekly_v1")
def build_player_stats_weekly_v1(settings: Settings) -> MartPlayerStatsWeeklyResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _source_columns(con)
        required = {"season", "week", "player_id"}
        missing = sorted(required - cols)
        if missing:
            raise ValueError(
                f"{_SOURCE_TABLE} is missing required columns: {', '.join(missing)}"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        player_join = _has_table(con, _PLAYER_TABLE)
        team_join = _has_table(con, _TEAM_TABLE)
        display_name_sql = "p.display_name" if player_join else "NULL"
        team_name_sql = "t.team_name" if team_join else "NULL"
        team_abbr_sql = "t.team_abbr" if team_join else "NULL"
        player_join_sql = (
            f"LEFT JOIN {_PLAYER_TABLE} p ON p.player_id = s.player_id"
            if player_join
            else ""
        )
        team_join_sql = (
            f"LEFT JOIN {_TEAM_TABLE} t ON t.team_id = s.team_id"
            if team_join
            else ""
        )

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_PLAYER_STATS_WEEKLY_V1} AS
            SELECT
                s.season,
                s.week,
                s.player_id,
                s.team_id,
                s.position,
                s.passing_yards,
                s.passing_tds,
                s.interceptions,
                s.rushing_yards,
                s.rushing_tds,
                s.receptions,
                s.receiving_yards,
                s.receiving_tds,
                s.touchdowns,
                s.fumbles_lost,
                COALESCE(s.passing_yards, 0)
                    + COALESCE(s.rushing_yards, 0)
                    + COALESCE(s.receiving_yards, 0) AS total_yards,
                COALESCE(s.touchdowns,
                    COALESCE(s.passing_tds, 0)
                    + COALESCE(s.rushing_tds, 0)
                    + COALESCE(s.receiving_tds, 0)) AS total_touchdowns,
                {display_name_sql} AS display_name,
                {team_name_sql} AS team_name,
                {team_abbr_sql} AS team_abbr,
                s._source_file_id AS source_file_id,
                s._adapter_id AS source_adapter_id,
                s._canonicalized_at AS source_canonicalized_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE} s
            {player_join_sql}
            {team_join_sql}
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_PLAYER_STATS_WEEKLY_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    return MartPlayerStatsWeeklyResult(
        qualified_table=MART_PLAYER_STATS_WEEKLY_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_PLAYER_STATS_WEEKLY_V1",
    "MartPlayerStatsWeeklyResult",
    "build_player_stats_weekly_v1",
]
