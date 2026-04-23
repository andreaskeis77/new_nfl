"""Mart builder for ``mart.roster_current_v1`` (T2.5D, ADR-0029 + ADR-0032).

Projection of ``core.roster_membership`` restricted to open intervals
(``valid_to_week IS NULL``) — the canonical "who is on the team right now"
read surface. Enriched with ``display_name`` (from ``core.player``) and
``team_name`` / ``team_abbr`` (from ``core.team``) when those tables exist,
otherwise the name columns fall back to ``NULL`` so the mart stays
rebuildable in environments that only have roster data staged.

UI/API read exclusively from this projection (ADR-0029).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.settings import Settings

MART_ROSTER_CURRENT_V1 = "mart.roster_current_v1"
_SOURCE_TABLE = "core.roster_membership"


@dataclass(frozen=True)
class MartRosterCurrentResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    built_at: datetime


def _table_exists(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, name],
    ).fetchone()
    return bool(row and int(row[0]) > 0)


@register_mart_builder("roster_current_v1")
def build_roster_current_v1(settings: Settings) -> MartRosterCurrentResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        if not _table_exists(con, "core", "roster_membership"):
            raise ValueError(
                f"{_SOURCE_TABLE} does not exist; run core-load --slice rosters "
                "--execute first"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        has_player = _table_exists(con, "core", "player")
        has_team = _table_exists(con, "core", "team")

        player_join = (
            "LEFT JOIN core.player p ON p.player_id = rm.player_id"
            if has_player
            else ""
        )
        team_join = (
            "LEFT JOIN core.team t ON t.team_id = rm.team_id"
            if has_team
            else ""
        )
        display_name = "p.display_name" if has_player else "NULL"
        team_name = "t.team_name" if has_team else "NULL"
        team_abbr = "t.team_abbr" if has_team else "NULL"

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_ROSTER_CURRENT_V1} AS
            SELECT
                rm.player_id,
                rm.team_id,
                rm.season,
                rm.valid_from_week,
                rm.valid_to_week,
                rm.last_observed_week,
                rm.global_max_week,
                rm.position,
                rm.jersey_number,
                rm.status,
                {display_name} AS display_name,
                {team_name} AS team_name,
                {team_abbr} AS team_abbr,
                LOWER(rm.player_id) AS player_id_lower,
                LOWER(rm.team_id) AS team_id_lower,
                rm._first_loaded_at,
                rm._last_loaded_at,
                rm._source_file_id AS source_file_id,
                rm._adapter_id AS source_adapter_id,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE} rm
            {player_join}
            {team_join}
            WHERE rm.valid_to_week IS NULL
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_ROSTER_CURRENT_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()
    return MartRosterCurrentResult(
        qualified_table=MART_ROSTER_CURRENT_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_ROSTER_CURRENT_V1",
    "MartRosterCurrentResult",
    "build_roster_current_v1",
]
