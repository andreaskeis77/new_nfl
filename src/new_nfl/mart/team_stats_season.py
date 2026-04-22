"""Mart builder for ``mart.team_stats_season_v1`` (T2.5E, ADR-0029 + ADR-0031).

Season aggregate of ``core.team_stats_weekly`` at the ``(season, team_id)``
grain. Summands are NULL-tolerant (``SUM`` ignores NULLs, which matches
bye-week semantics) and the ``games_played`` count uses
``COUNT(points_for)`` so a missing weekly row (bye, not yet played) is not
counted as a game. Derived ``point_diff`` and ``yard_diff`` mirror the
weekly-mart shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.settings import Settings

MART_TEAM_STATS_SEASON_V1 = "mart.team_stats_season_v1"
_SOURCE_TABLE = "core.team_stats_weekly"
_TEAM_TABLE = "core.team"


@dataclass(frozen=True)
class MartTeamStatsSeasonResult:
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
            "team_stats_weekly --execute first"
        ) from exc
    return {str(r[0]).strip().lower() for r in rows}


def _has_table(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return False
    return True


def build_team_stats_season_v1(settings: Settings) -> MartTeamStatsSeasonResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _source_columns(con)
        required = {"season", "week", "team_id"}
        missing = sorted(required - cols)
        if missing:
            raise ValueError(
                f"{_SOURCE_TABLE} is missing required columns: {', '.join(missing)}"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        team_join = _has_table(con, _TEAM_TABLE)
        team_name_sql = "t.team_name" if team_join else "NULL"
        team_abbr_sql = "t.team_abbr" if team_join else "NULL"
        join_sql = (
            f"LEFT JOIN {_TEAM_TABLE} t ON t.team_id = agg.team_id"
            if team_join
            else ""
        )

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_TEAM_STATS_SEASON_V1} AS
            WITH agg AS (
                SELECT
                    season,
                    team_id,
                    COUNT(points_for) AS games_played,
                    SUM(points_for) AS points_for,
                    SUM(points_against) AS points_against,
                    SUM(yards_for) AS yards_for,
                    SUM(yards_against) AS yards_against,
                    SUM(turnovers) AS turnovers,
                    SUM(penalties_for) AS penalties_for
                FROM {_SOURCE_TABLE}
                GROUP BY season, team_id
            )
            SELECT
                agg.season,
                agg.team_id,
                agg.games_played,
                agg.points_for,
                agg.points_against,
                agg.yards_for,
                agg.yards_against,
                agg.turnovers,
                agg.penalties_for,
                CASE
                    WHEN agg.points_for IS NOT NULL AND agg.points_against IS NOT NULL
                    THEN agg.points_for - agg.points_against
                END AS point_diff,
                CASE
                    WHEN agg.yards_for IS NOT NULL AND agg.yards_against IS NOT NULL
                    THEN agg.yards_for - agg.yards_against
                END AS yard_diff,
                {team_name_sql} AS team_name,
                {team_abbr_sql} AS team_abbr,
                CURRENT_TIMESTAMP AS built_at
            FROM agg
            {join_sql}
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_TEAM_STATS_SEASON_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    return MartTeamStatsSeasonResult(
        qualified_table=MART_TEAM_STATS_SEASON_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_TEAM_STATS_SEASON_V1",
    "MartTeamStatsSeasonResult",
    "build_team_stats_season_v1",
]
