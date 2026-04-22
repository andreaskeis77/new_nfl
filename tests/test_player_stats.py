"""T2.5F Player Stats domain — second aggregating core promotion, three-mart
rebuild (weekly passthrough + season aggregate + career aggregate), Tier-A
vs Tier-B conflict surface at the (season, week, player_id) grain, operator
override flow, multi-position player edge case (Taysom Hill)."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.player_stats import (
    CORE_PLAYER_STATS_WEEKLY_TABLE,
    CorePlayerStatsLoadResult,
    execute_core_player_stats_load,
)
from new_nfl.core.result import CoreLoadResultLike
from new_nfl.core_load import execute_core_load
from new_nfl.jobs.quarantine import (
    list_quarantine_cases,
    resolve_quarantine_case,
)
from new_nfl.mart.player_stats_career import MART_PLAYER_STATS_CAREER_V1
from new_nfl.mart.player_stats_season import MART_PLAYER_STATS_SEASON_V1
from new_nfl.mart.player_stats_weekly import MART_PLAYER_STATS_WEEKLY_V1
from new_nfl.metadata import seed_default_sources
from new_nfl.settings import Settings


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    repo_root = tmp_path / 'repo'
    data_root = repo_root / 'data'
    db_path = data_root / 'db' / 'new_nfl.duckdb'
    repo_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        repo_root=repo_root,
        env='test',
        data_root=data_root,
        db_path=db_path,
    )


def _bootstrap(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)


# Row shape: (player_id, season, week, team_id, position,
#             passing_yards, passing_tds, interceptions,
#             rushing_yards, rushing_tds,
#             receptions, receiving_yards, receiving_tds,
#             touchdowns, fumbles_lost)
StatRow = tuple[
    str, int, int, str, str,
    int, int, int,
    int, int,
    int, int, int,
    int, int,
]


def _create_stage_table(con: duckdb.DuckDBPyConnection, qualified_table: str) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS stg')
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {qualified_table} (
            player_id VARCHAR,
            season VARCHAR,
            week VARCHAR,
            team_id VARCHAR,
            position VARCHAR,
            passing_yards VARCHAR,
            passing_tds VARCHAR,
            interceptions VARCHAR,
            rushing_yards VARCHAR,
            rushing_tds VARCHAR,
            receptions VARCHAR,
            receiving_yards VARCHAR,
            receiving_tds VARCHAR,
            touchdowns VARCHAR,
            fumbles_lost VARCHAR,
            _source_file_id VARCHAR,
            _adapter_id VARCHAR,
            _loaded_at TIMESTAMP
        )
        """
    )


def _seed_tier_a_stage(settings: Settings, rows: list[StatRow]) -> None:
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'player_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        _create_stage_table(con, primary.stage_qualified_table)
        for row in rows:
            (
                pid, season, week, team, pos,
                py, ptd, ints,
                ry, rtd,
                rec, recy, rectd,
                tds, fl,
            ) = row
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'sf-ps-a-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [
                    pid, str(season), str(week), team, pos,
                    str(py), str(ptd), str(ints),
                    str(ry), str(rtd),
                    str(rec), str(recy), str(rectd),
                    str(tds), str(fl),
                    primary.adapter_id,
                ],
            )
    finally:
        con.close()


def _seed_tier_b_stage(settings: Settings, rows: list[StatRow]) -> None:
    cross = get_slice('official_context_web', 'player_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        _create_stage_table(con, cross.stage_qualified_table)
        for row in rows:
            (
                pid, season, week, team, pos,
                py, ptd, ints,
                ry, rtd,
                rec, recy, rectd,
                tds, fl,
            ) = row
            con.execute(
                f"""
                INSERT INTO {cross.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'sf-ps-b-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [
                    pid, str(season), str(week), team, pos,
                    str(py), str(ptd), str(ints),
                    str(ry), str(rtd),
                    str(rec), str(recy), str(rectd),
                    str(tds), str(fl),
                    cross.adapter_id,
                ],
            )
    finally:
        con.close()


def _fetch_core_rows(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT player_id, season, week, team_id, position,
                   passing_yards, passing_tds, rushing_yards, rushing_tds,
                   receiving_yards, receiving_tds, touchdowns, fumbles_lost
            FROM {CORE_PLAYER_STATS_WEEKLY_TABLE}
            ORDER BY player_id, season, week
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'player_id', 'season', 'week', 'team_id', 'position',
        'passing_yards', 'passing_tds', 'rushing_yards', 'rushing_tds',
        'receiving_yards', 'receiving_tds', 'touchdowns', 'fumbles_lost',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _fetch_weekly_mart(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT player_id, season, week, position,
                   passing_yards, rushing_yards, receiving_yards,
                   total_yards, total_touchdowns
            FROM {MART_PLAYER_STATS_WEEKLY_V1}
            ORDER BY player_id, season, week
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'player_id', 'season', 'week', 'position',
        'passing_yards', 'rushing_yards', 'receiving_yards',
        'total_yards', 'total_touchdowns',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _fetch_season_mart(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT player_id, season, primary_position, games_played,
                   passing_yards, rushing_yards, receiving_yards,
                   touchdowns, total_yards, total_touchdowns
            FROM {MART_PLAYER_STATS_SEASON_V1}
            ORDER BY player_id, season
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'player_id', 'season', 'primary_position', 'games_played',
        'passing_yards', 'rushing_yards', 'receiving_yards',
        'touchdowns', 'total_yards', 'total_touchdowns',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _fetch_career_mart(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT player_id, first_season, last_season, seasons_played,
                   games_played, passing_yards, rushing_yards,
                   receiving_yards, total_yards, total_touchdowns
            FROM {MART_PLAYER_STATS_CAREER_V1}
            ORDER BY player_id
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'player_id', 'first_season', 'last_season', 'seasons_played',
        'games_played', 'passing_yards', 'rushing_yards',
        'receiving_yards', 'total_yards', 'total_touchdowns',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_core_player_stats_dry_run_profiles_without_writing(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             300, 3, 0, 40, 1, 0, 0, 0, 4, 0),
            ('00-0033873', 2024, 2, 'KC', 'QB',
             280, 2, 1, 20, 0, 0, 0, 0, 2, 1),
        ],
    )
    result = execute_core_player_stats_load(settings, execute=False)
    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_player_stats_load'
    assert result.source_row_count == 2
    assert result.distinct_player_season_week_count == 2
    assert result.row_count == 0
    assert result.mart_qualified_table == ''
    assert result.season_mart_qualified_table == ''
    assert result.career_mart_qualified_table == ''
    con = duckdb.connect(str(settings.db_path))
    try:
        tables = {row[0] for row in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'core'"
        ).fetchall()}
    finally:
        con.close()
    assert 'player_stats_weekly' not in tables


def test_core_player_stats_execute_builds_all_three_marts(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             300, 3, 0, 40, 1, 0, 0, 0, 4, 0),
            ('00-0033873', 2024, 2, 'KC', 'QB',
             280, 2, 1, 20, 0, 0, 0, 0, 2, 1),
            ('00-0033873', 2024, 3, 'KC', 'QB',
             350, 4, 0, 15, 0, 0, 0, 0, 4, 0),
            ('00-0030506', 2024, 1, 'SF', 'RB',
             0, 0, 0, 120, 2, 3, 25, 0, 2, 0),
            ('00-0030506', 2024, 2, 'SF', 'RB',
             0, 0, 0, 95, 1, 2, 18, 0, 1, 1),
        ],
    )
    result = execute_core_player_stats_load(settings, execute=True)
    assert result.run_mode == 'execute'
    assert result.run_status == 'core_player_stats_weekly_loaded'
    assert result.row_count == 5
    assert result.distinct_player_season_week_count == 5
    assert result.mart_qualified_table == MART_PLAYER_STATS_WEEKLY_V1
    assert result.mart_row_count == 5
    assert result.season_mart_qualified_table == MART_PLAYER_STATS_SEASON_V1
    assert result.season_mart_row_count == 2
    assert result.career_mart_qualified_table == MART_PLAYER_STATS_CAREER_V1
    assert result.career_mart_row_count == 2

    weekly = _fetch_weekly_mart(settings)
    mahomes_week1 = next(
        r for r in weekly
        if r['player_id'] == '00-0033873' and r['week'] == 1
    )
    # total_yards = passing + rushing + receiving = 300 + 40 + 0
    assert mahomes_week1['total_yards'] == 340
    assert mahomes_week1['total_touchdowns'] == 4

    season = _fetch_season_mart(settings)
    mahomes_season = next(r for r in season if r['player_id'] == '00-0033873')
    assert mahomes_season['games_played'] == 3
    assert mahomes_season['primary_position'] == 'QB'
    assert mahomes_season['passing_yards'] == 930
    assert mahomes_season['touchdowns'] == 10

    career = _fetch_career_mart(settings)
    mccaffrey_career = next(r for r in career if r['player_id'] == '00-0030506')
    assert mccaffrey_career['first_season'] == 2024
    assert mccaffrey_career['last_season'] == 2024
    assert mccaffrey_career['seasons_played'] == 1
    assert mccaffrey_career['rushing_yards'] == 215
    assert mccaffrey_career['receiving_yards'] == 43


def test_taysom_hill_multi_position_career_aggregates_across_positions(
    settings: Settings,
) -> None:
    """Taysom Hill weeks: week 1 as QB (passing), week 2 as TE (receiving),
    week 3 as RB (rushing). Season + career aggregate across all positions."""
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033357', 2023, 1, 'NO', 'QB',
             180, 1, 0, 25, 0, 0, 0, 0, 1, 0),
            ('00-0033357', 2023, 2, 'NO', 'TE',
             0, 0, 0, 10, 0, 4, 55, 1, 1, 0),
            ('00-0033357', 2023, 3, 'NO', 'RB',
             0, 0, 0, 80, 2, 1, 12, 0, 2, 0),
            ('00-0033357', 2024, 1, 'NO', 'TE',
             0, 0, 0, 5, 0, 3, 40, 0, 0, 0),
        ],
    )
    result = execute_core_player_stats_load(settings, execute=True)
    assert result.row_count == 4

    season = _fetch_season_mart(settings)
    hill_2023 = next(
        r for r in season
        if r['player_id'] == '00-0033357' and r['season'] == 2023
    )
    assert hill_2023['games_played'] == 3
    # Aggregate is position-agnostic
    assert hill_2023['passing_yards'] == 180
    assert hill_2023['rushing_yards'] == 115
    assert hill_2023['receiving_yards'] == 67
    assert hill_2023['touchdowns'] == 4
    # primary_position = MODE over (QB, TE, RB) — MODE returns first-seen on tie
    assert hill_2023['primary_position'] in ('QB', 'TE', 'RB')

    career = _fetch_career_mart(settings)
    hill = next(r for r in career if r['player_id'] == '00-0033357')
    assert hill['first_season'] == 2023
    assert hill['last_season'] == 2024
    assert hill['seasons_played'] == 2
    assert hill['games_played'] == 4
    assert hill['passing_yards'] == 180
    assert hill['rushing_yards'] == 120
    assert hill['receiving_yards'] == 107


def test_duplicate_player_week_rows_dedupe_by_loaded_at(settings: Settings) -> None:
    """Two stage rows for the same (season, week, player_id) — latest _loaded_at wins."""
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'player_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        _create_stage_table(con, primary.stage_qualified_table)
        # older row
        con.execute(
            f"""INSERT INTO {primary.stage_qualified_table} VALUES (
                '00-0033873','2024','1','KC','QB',
                '250','2','1','30','0','0','0','0','2','1',
                'sf-old','nflverse_bulk',TIMESTAMP '2024-09-08 12:00:00'
            )"""
        )
        # corrected row
        con.execute(
            f"""INSERT INTO {primary.stage_qualified_table} VALUES (
                '00-0033873','2024','1','KC','QB',
                '300','3','0','40','1','0','0','0','4','0',
                'sf-corrected','nflverse_bulk',TIMESTAMP '2024-09-10 09:00:00'
            )"""
        )
    finally:
        con.close()
    result = execute_core_player_stats_load(settings, execute=True)
    assert result.row_count == 1
    rows = _fetch_core_rows(settings)
    assert len(rows) == 1
    assert rows[0]['passing_yards'] == 300
    assert rows[0]['touchdowns'] == 4


def test_tier_b_disagreement_on_passing_yards_opens_quarantine(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             300, 3, 0, 40, 1, 0, 0, 0, 4, 0),
        ],
    )
    _seed_tier_b_stage(
        settings,
        [
            # Tier-B disagrees on passing_yards (290 vs 300).
            ('00-0033873', 2024, 1, 'KC', 'QB',
             290, 3, 0, 40, 1, 0, 0, 0, 4, 0),
        ],
    )
    result = execute_core_player_stats_load(settings, execute=True)
    assert result.conflict_count == 1
    assert len(result.opened_quarantine_case_ids) == 1
    cases = list_quarantine_cases(settings, status_filter='open')
    assert any(c.scope_ref == '00-0033873:2024:W01' for c in cases)
    # Tier-A wins in core.player_stats_weekly.
    rows = _fetch_core_rows(settings)
    assert rows[0]['passing_yards'] == 300


def test_core_load_dispatch_routes_player_stats_slice(settings: Settings) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             300, 3, 0, 40, 1, 0, 0, 0, 4, 0),
        ],
    )
    result = execute_core_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        slice_key='player_stats_weekly',
    )
    assert isinstance(result, CorePlayerStatsLoadResult)
    assert result.qualified_table == CORE_PLAYER_STATS_WEEKLY_TABLE
    assert result.mart_qualified_table == MART_PLAYER_STATS_WEEKLY_V1
    assert result.season_mart_qualified_table == MART_PLAYER_STATS_SEASON_V1
    assert result.career_mart_qualified_table == MART_PLAYER_STATS_CAREER_V1


def test_operator_override_resolves_player_stats_quarantine(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             300, 3, 0, 40, 1, 0, 0, 0, 4, 0),
        ],
    )
    _seed_tier_b_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             290, 3, 0, 40, 1, 0, 0, 0, 4, 0),
        ],
    )
    result = execute_core_player_stats_load(settings, execute=True)
    case_id = result.opened_quarantine_case_ids[0]
    resolve_quarantine_case(
        settings,
        quarantine_case_id=case_id,
        action='override',
        triggered_by='andreas',
        note='Tier-A value wins; Tier-B feed lagging',
    )
    cases = list_quarantine_cases(settings, status_filter='open')
    assert not any(c.quarantine_case_id == case_id for c in cases)


def test_core_player_stats_result_satisfies_core_load_protocol(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 2024, 1, 'KC', 'QB',
             300, 3, 0, 40, 1, 0, 0, 0, 4, 0),
        ],
    )
    result = execute_core_player_stats_load(settings, execute=True)
    assert isinstance(result, CoreLoadResultLike)
    for attr in (
        'run_mode', 'run_status', 'pipeline_name', 'ingest_run_id',
        'qualified_table', 'source_row_count', 'row_count',
        'invalid_row_count', 'load_event_id', 'mart_qualified_table',
        'mart_row_count',
    ):
        assert hasattr(result, attr), f'missing {attr}'
