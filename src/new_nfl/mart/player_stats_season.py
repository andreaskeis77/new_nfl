"""Mart builder for ``mart.player_stats_season_v1`` (T2.5F, ADR-0029 + ADR-0031).

Season aggregate of ``core.player_stats_weekly`` at the ``(season, player_id)``
grain. Summands are NULL-tolerant (``SUM`` ignores NULLs, which matches
bye-week semantics) and the ``games_played`` count uses
``COUNT(CASE WHEN <has-any-stat> THEN 1 END)`` so a zero-stat weekly row
(scratched, IR) still counts if that row exists, but a missing weekly row
(bye, never rostered) is not counted. Multi-position players (Taysom Hill)
are handled by aggregating across all weekly rows for the same ``player_id``
regardless of rostered ``position``; the aggregate reports ``primary_position``
as the MODE over the season.

Note: this mart trusts the upstream to filter regular-season weeks. For
playoff separation a ``week <= 18`` filter or a ``season_type`` join will
be needed in T2.6 UI work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.settings import Settings

MART_PLAYER_STATS_SEASON_V1 = "mart.player_stats_season_v1"
_SOURCE_TABLE = "core.player_stats_weekly"
_PLAYER_TABLE = "core.player"


@dataclass(frozen=True)
class MartPlayerStatsSeasonResult:
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


def build_player_stats_season_v1(settings: Settings) -> MartPlayerStatsSeasonResult:
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
        join_sql = (
            f"LEFT JOIN {_PLAYER_TABLE} p ON p.player_id = agg.player_id"
            if player_join
            else ""
        )

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_PLAYER_STATS_SEASON_V1} AS
            WITH agg AS (
                SELECT
                    season,
                    player_id,
                    MODE(position) AS primary_position,
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
                GROUP BY season, player_id
            )
            SELECT
                agg.season,
                agg.player_id,
                agg.primary_position,
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
                CURRENT_TIMESTAMP AS built_at
            FROM agg
            {join_sql}
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_PLAYER_STATS_SEASON_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    return MartPlayerStatsSeasonResult(
        qualified_table=MART_PLAYER_STATS_SEASON_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_PLAYER_STATS_SEASON_V1",
    "MartPlayerStatsSeasonResult",
    "build_player_stats_season_v1",
]
