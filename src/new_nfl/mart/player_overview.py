"""Mart builder for ``mart.player_overview_v1`` (T2.5C, ADR-0029 + ADR-0031).

Denormalized read projection of ``core.player``. Full rebuild via
``CREATE OR REPLACE TABLE``. Adds pre-lowercased filter columns, derived
``is_active`` flag (``last_season IS NULL``), ``full_name`` fallback
(``display_name`` if populated, else ``first_name || ' ' || last_name``) and
``position_is_known`` flag derived from the ontology ``position`` value set
when the active ontology is loaded. UI/API read exclusively from this
projection (ADR-0029).

The ontology lookup is best-effort: if :mod:`new_nfl.ontology` has no active
version (fresh environment, tests without ontology load), the flag falls back
to ``NULL`` silently — the projection stays rebuildable either way.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.meta import schema_cache
from new_nfl.settings import Settings

MART_PLAYER_OVERVIEW_V1 = "mart.player_overview_v1"
_SOURCE_TABLE = "core.player"


@dataclass(frozen=True)
class MartPlayerOverviewResult:
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
            f"{_SOURCE_TABLE} does not exist; run core-load --slice players "
            "--execute first"
        ) from exc
    return {str(r[0]).strip().lower() for r in rows}


def _opt(name: str, present: set[str]) -> str:
    return name if name in present else "NULL"


def _known_position_values(con: duckdb.DuckDBPyConnection) -> set[str]:
    """Best-effort ontology lookup for known positions.

    Returns the set of uppercase ``position`` values declared in the active
    ontology version's ``position`` value set. If ontology tables or rows
    are missing, returns an empty set — the caller treats that as "unknown
    ontology, flag position_is_known NULL".
    """
    try:
        rows = con.execute(
            """
            WITH active AS (
                SELECT ontology_version_id
                FROM meta.ontology_version
                WHERE is_active = TRUE
                LIMIT 1
            ),
            pos_term AS (
                SELECT t.ontology_term_id
                FROM meta.ontology_term t
                JOIN active a ON a.ontology_version_id = t.ontology_version_id
                WHERE LOWER(t.term_key) = 'position'
                LIMIT 1
            ),
            pos_value_set AS (
                SELECT vs.ontology_value_set_id
                FROM meta.ontology_value_set vs
                JOIN pos_term pt ON pt.ontology_term_id = vs.ontology_term_id
            )
            SELECT UPPER(TRIM(m.value))
            FROM meta.ontology_value_set_member m
            JOIN pos_value_set pvs
              ON pvs.ontology_value_set_id = m.ontology_value_set_id
            WHERE NULLIF(TRIM(m.value), '') IS NOT NULL
            """
        ).fetchall()
    except duckdb.Error:
        return set()
    return {str(row[0]) for row in rows if row and row[0] is not None}


@register_mart_builder("player_overview_v1")
def build_player_overview_v1(settings: Settings) -> MartPlayerOverviewResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _source_columns(settings, con)
        required = {"player_id", "display_name"}
        missing = sorted(required - cols)
        if missing:
            raise ValueError(
                f"{_SOURCE_TABLE} is missing required columns: {', '.join(missing)}"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        first_name = _opt("first_name", cols)
        last_name = _opt("last_name", cols)
        birth_date = _opt("birth_date", cols)
        position = _opt("position", cols)
        height = _opt("height", cols)
        weight = _opt("weight", cols)
        college_name = _opt("college_name", cols)
        rookie_season = _opt("rookie_season", cols)
        last_season = _opt("last_season", cols)
        current_team_id = _opt("current_team_id", cols)
        jersey_number = _opt("jersey_number", cols)
        draft_club = _opt("draft_club", cols)
        draft_year = _opt("draft_year", cols)
        draft_round = _opt("draft_round", cols)
        draft_pick = _opt("draft_pick", cols)
        status_col = _opt("status", cols)
        source_file_id = _opt("_source_file_id", cols)
        adapter_id = _opt("_adapter_id", cols)
        canonicalized_at = _opt("_canonicalized_at", cols)

        known = _known_position_values(con)
        if known and position != "NULL":
            values_sql = ", ".join(f"'{v}'" for v in sorted(known))
            position_is_known = (
                f"CASE "
                f"WHEN {position} IS NULL THEN NULL "
                f"WHEN UPPER({position}) IN ({values_sql}) THEN TRUE "
                f"ELSE FALSE END"
            )
        else:
            position_is_known = "NULL"

        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_PLAYER_OVERVIEW_V1} AS
            SELECT
                player_id,
                display_name,
                {first_name} AS first_name,
                {last_name} AS last_name,
                COALESCE(
                    NULLIF(display_name, ''),
                    TRIM(
                        CONCAT(
                            COALESCE({first_name}, ''),
                            CASE
                                WHEN {first_name} IS NOT NULL AND {last_name} IS NOT NULL
                                    THEN ' ' ELSE ''
                            END,
                            COALESCE({last_name}, '')
                        )
                    )
                ) AS full_name,
                {birth_date} AS birth_date,
                {position} AS position,
                {height} AS height,
                {weight} AS weight,
                {college_name} AS college_name,
                {rookie_season} AS rookie_season,
                {last_season} AS last_season,
                {current_team_id} AS current_team_id,
                {jersey_number} AS jersey_number,
                {draft_club} AS draft_club,
                {draft_year} AS draft_year,
                {draft_round} AS draft_round,
                {draft_pick} AS draft_pick,
                {status_col} AS status,
                LOWER(player_id) AS player_id_lower,
                LOWER(COALESCE(display_name, '')) AS display_name_lower,
                LOWER(COALESCE(CAST({position} AS VARCHAR), '')) AS position_lower,
                LOWER(COALESCE(CAST({current_team_id} AS VARCHAR), '')) AS current_team_id_lower,
                CASE WHEN {last_season} IS NULL THEN TRUE ELSE FALSE END AS is_active,
                {position_is_known} AS position_is_known,
                {source_file_id} AS source_file_id,
                {adapter_id} AS source_adapter_id,
                {canonicalized_at} AS source_canonicalized_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE}
            """
        )
        row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {MART_PLAYER_OVERVIEW_V1}").fetchone()[0]
        )
    finally:
        con.close()
    built_at = datetime.now()
    return MartPlayerOverviewResult(
        qualified_table=MART_PLAYER_OVERVIEW_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=built_at,
    )


__all__ = [
    "MART_PLAYER_OVERVIEW_V1",
    "MartPlayerOverviewResult",
    "build_player_overview_v1",
]
