"""Mart builder for ``mart.team_stats_weekly_v1`` (T2.5E, ADR-0029 + ADR-0031).

Read projection of ``core.team_stats_weekly`` at the original
``(season, week, team_id)`` grain. Adds derived ``point_diff`` and
``yard_diff`` columns plus best-effort LEFT JOIN on ``core.team`` for
``team_name``/``team_abbr`` (NULL when ``core.team`` has not been loaded).
UI/API read exclusively from this projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.settings import Settings

MART_TEAM_STATS_WEEKLY_V1 = "mart.team_stats_weekly_v1"
_SOURCE_TABLE = "core.team_stats_weekly"
_TEAM_TABLE = "core.team"


@dataclass(frozen=True)
class MartTeamStatsWeeklyResult:
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


@register_mart_builder("team_stats_weekly_v1")
def build_team_stats_weekly_v1(settings: Settings) -> MartTeamStatsWeeklyResult:
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
            f"LEFT JOIN {_TEAM_TABLE} t ON t.team_id = s.team_id"
            if team_join
            else ""
        )

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_TEAM_STATS_WEEKLY_V1} AS
            SELECT
                s.season,
                s.week,
                s.team_id,
                s.opponent_team_id,
                s.points_for,
                s.points_against,
                s.yards_for,
                s.yards_against,
                s.turnovers,
                s.penalties_for,
                CASE
                    WHEN s.points_for IS NOT NULL AND s.points_against IS NOT NULL
                    THEN s.points_for - s.points_against
                END AS point_diff,
                CASE
                    WHEN s.yards_for IS NOT NULL AND s.yards_against IS NOT NULL
                    THEN s.yards_for - s.yards_against
                END AS yard_diff,
                {team_name_sql} AS team_name,
                {team_abbr_sql} AS team_abbr,
                s._source_file_id AS source_file_id,
                s._adapter_id AS source_adapter_id,
                s._canonicalized_at AS source_canonicalized_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE} s
            {join_sql}
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_TEAM_STATS_WEEKLY_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    return MartTeamStatsWeeklyResult(
        qualified_table=MART_TEAM_STATS_WEEKLY_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_TEAM_STATS_WEEKLY_V1",
    "MartTeamStatsWeeklyResult",
    "build_team_stats_weekly_v1",
]
