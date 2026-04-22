"""Mart builder for ``mart.player_stats_career_v1`` (T2.5F, ADR-0029 + ADR-0031).

Career aggregate of ``core.player_stats_weekly`` at the ``player_id`` grain
(sum across all seasons). Unlike the season mart this projection does not
aggregate by position; every weekly row the player appears on contributes
to the career totals. ``seasons_played`` is a ``COUNT(DISTINCT season)``
filtered by the same has-any-stat predicate the season mart uses so that
scratched seasons (rostered, zero stats across all weeks) do not pad the
career count.

Best-effort LEFT JOIN on ``core.player`` enriches ``display_name`` /
``position`` (the current rostered position, which may differ from
historical weekly positions).

Note: career totals pool regular + postseason until T2.6 adds a
``season_type`` filter path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.settings import Settings

MART_PLAYER_STATS_CAREER_V1 = "mart.player_stats_career_v1"
_SOURCE_TABLE = "core.player_stats_weekly"
_PLAYER_TABLE = "core.player"


@dataclass(frozen=True)
class MartPlayerStatsCareerResult:
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


def build_player_stats_career_v1(settings: Settings) -> MartPlayerStatsCareerResult:
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
        display_name_sql = "p.display_name" if player_join else "NULL"
        position_sql = "p.position" if player_join else "NULL"
        join_sql = (
            f"LEFT JOIN {_PLAYER_TABLE} p ON p.player_id = agg.player_id"
            if player_join
            else ""
        )

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_PLAYER_STATS_CAREER_V1} AS
            WITH agg AS (
                SELECT
                    player_id,
                    MIN(season) AS first_season,
                    MAX(season) AS last_season,
                    COUNT(DISTINCT CASE
                        WHEN passing_yards IS NOT NULL
                          OR rushing_yards IS NOT NULL
                          OR receiving_yards IS NOT NULL
                          OR touchdowns IS NOT NULL
                        THEN season END
                    ) AS seasons_played,
                    COUNT(
                        CASE WHEN passing_yards IS NOT NULL
                             OR rushing_yards IS NOT NULL
                             OR receiving_yards IS NOT NULL
                             OR touchdowns IS NOT NULL
                          THEN 1 END
                    ) AS games_played,
                    SUM(passing_yards) AS passing_yards,
                    SUM(passing_tds) AS passing_tds,
                    SUM(interceptions) AS interceptions,
                    SUM(rushing_yards) AS rushing_yards,
                    SUM(rushing_tds) AS rushing_tds,
                    SUM(receptions) AS receptions,
                    SUM(receiving_yards) AS receiving_yards,
                    SUM(receiving_tds) AS receiving_tds,
                    SUM(touchdowns) AS touchdowns,
                    SUM(fumbles_lost) AS fumbles_lost
                FROM {_SOURCE_TABLE}
                GROUP BY player_id
            )
            SELECT
                agg.player_id,
                agg.first_season,
                agg.last_season,
                agg.seasons_played,
                agg.games_played,
                agg.passing_yards,
                agg.passing_tds,
                agg.interceptions,
                agg.rushing_yards,
                agg.rushing_tds,
                agg.receptions,
                agg.receiving_yards,
                agg.receiving_tds,
                agg.touchdowns,
                agg.fumbles_lost,
                COALESCE(agg.passing_yards, 0)
                    + COALESCE(agg.rushing_yards, 0)
                    + COALESCE(agg.receiving_yards, 0) AS total_yards,
                COALESCE(agg.touchdowns,
                    COALESCE(agg.passing_tds, 0)
                    + COALESCE(agg.rushing_tds, 0)
                    + COALESCE(agg.receiving_tds, 0)) AS total_touchdowns,
                {display_name_sql} AS display_name,
                {position_sql} AS current_position,
                CURRENT_TIMESTAMP AS built_at
            FROM agg
            {join_sql}
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_PLAYER_STATS_CAREER_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    return MartPlayerStatsCareerResult(
        qualified_table=MART_PLAYER_STATS_CAREER_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_PLAYER_STATS_CAREER_V1",
    "MartPlayerStatsCareerResult",
    "build_player_stats_career_v1",
]
