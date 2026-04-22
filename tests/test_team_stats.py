"""T2.5E Team Stats domain — first aggregating core promotion, two-mart
rebuild (weekly passthrough + season aggregate), Tier-A vs Tier-B conflict
surface at the (season, week, team_id) grain, operator override flow."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.result import CoreLoadResultLike
from new_nfl.core.team_stats import (
    CORE_TEAM_STATS_WEEKLY_TABLE,
    CoreTeamStatsLoadResult,
    execute_core_team_stats_load,
)
from new_nfl.core_load import execute_core_load
from new_nfl.jobs.quarantine import (
    list_quarantine_cases,
    resolve_quarantine_case,
)
from new_nfl.mart.team_stats_season import MART_TEAM_STATS_SEASON_V1
from new_nfl.mart.team_stats_weekly import MART_TEAM_STATS_WEEKLY_V1
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


# Row shape: (team_id, season, week, opponent, points_for, points_against,
#            yards_for, yards_against, turnovers, penalties_for)
StatRow = tuple[str, int, int, str, int, int, int, int, int, int]


def _seed_tier_a_stage(settings: Settings, rows: list[StatRow]) -> None:
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'team_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                team_id VARCHAR,
                season VARCHAR,
                week VARCHAR,
                opponent_team_id VARCHAR,
                points_for VARCHAR,
                points_against VARCHAR,
                yards_for VARCHAR,
                yards_against VARCHAR,
                turnovers VARCHAR,
                penalties_for VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        for row in rows:
            (team, season, week, opp, pf, pa, yf, ya, to, pen) = row
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'sf-ts-a-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [
                    team, str(season), str(week), opp,
                    str(pf), str(pa), str(yf), str(ya), str(to), str(pen),
                    primary.adapter_id,
                ],
            )
    finally:
        con.close()


def _seed_tier_b_stage(settings: Settings, rows: list[StatRow]) -> None:
    cross = get_slice('official_context_web', 'team_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {cross.stage_qualified_table} (
                team_id VARCHAR,
                season VARCHAR,
                week VARCHAR,
                opponent_team_id VARCHAR,
                points_for VARCHAR,
                points_against VARCHAR,
                yards_for VARCHAR,
                yards_against VARCHAR,
                turnovers VARCHAR,
                penalties_for VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        for row in rows:
            (team, season, week, opp, pf, pa, yf, ya, to, pen) = row
            con.execute(
                f"""
                INSERT INTO {cross.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'sf-ts-b-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [
                    team, str(season), str(week), opp,
                    str(pf), str(pa), str(yf), str(ya), str(to), str(pen),
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
            SELECT team_id, season, week, opponent_team_id,
                   points_for, points_against, yards_for, yards_against,
                   turnovers, penalties_for
            FROM {CORE_TEAM_STATS_WEEKLY_TABLE}
            ORDER BY team_id, season, week
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'team_id', 'season', 'week', 'opponent_team_id',
        'points_for', 'points_against', 'yards_for', 'yards_against',
        'turnovers', 'penalties_for',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _fetch_weekly_mart(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT team_id, season, week, points_for, points_against,
                   point_diff, yard_diff
            FROM {MART_TEAM_STATS_WEEKLY_V1}
            ORDER BY team_id, season, week
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'team_id', 'season', 'week', 'points_for', 'points_against',
        'point_diff', 'yard_diff',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _fetch_season_mart(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT team_id, season, games_played, points_for, points_against,
                   point_diff, yards_for, yard_diff, turnovers
            FROM {MART_TEAM_STATS_SEASON_V1}
            ORDER BY team_id, season
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'team_id', 'season', 'games_played', 'points_for', 'points_against',
        'point_diff', 'yards_for', 'yard_diff', 'turnovers',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_core_team_stats_dry_run_profiles_without_writing(settings: Settings) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 27, 20, 380, 340, 1, 5),
            ('KC', 2024, 2, 'CIN', 26, 25, 310, 300, 2, 8),
        ],
    )
    result = execute_core_team_stats_load(settings, execute=False)
    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_team_stats_load'
    assert result.source_row_count == 2
    assert result.distinct_team_season_week_count == 2
    assert result.row_count == 0
    assert result.mart_qualified_table == ''
    assert result.season_mart_qualified_table == ''
    con = duckdb.connect(str(settings.db_path))
    try:
        tables = {row[0] for row in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'core'"
        ).fetchall()}
    finally:
        con.close()
    assert 'team_stats_weekly' not in tables


def test_core_team_stats_execute_builds_weekly_and_season_marts(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 27, 20, 380, 340, 1, 5),
            ('KC', 2024, 2, 'CIN', 26, 25, 310, 300, 2, 8),
            ('KC', 2024, 3, 'ATL', 22, 17, 400, 330, 0, 4),
            ('BAL', 2024, 1, 'KC', 20, 27, 310, 380, 2, 6),
            ('BAL', 2024, 2, 'LV', 26, 23, 410, 290, 0, 3),
        ],
    )
    result = execute_core_team_stats_load(settings, execute=True)
    assert result.run_mode == 'execute'
    assert result.run_status == 'core_team_stats_weekly_loaded'
    assert result.row_count == 5
    assert result.distinct_team_season_week_count == 5
    assert result.mart_qualified_table == MART_TEAM_STATS_WEEKLY_V1
    assert result.mart_row_count == 5
    assert result.season_mart_qualified_table == MART_TEAM_STATS_SEASON_V1
    assert result.season_mart_row_count == 2

    weekly = _fetch_weekly_mart(settings)
    kc_week1 = next(r for r in weekly if r['team_id'] == 'KC' and r['week'] == 1)
    assert kc_week1['point_diff'] == 7
    assert kc_week1['yard_diff'] == 40

    season = _fetch_season_mart(settings)
    kc_season = next(r for r in season if r['team_id'] == 'KC')
    assert kc_season['games_played'] == 3
    assert kc_season['points_for'] == 75
    assert kc_season['points_against'] == 62
    assert kc_season['point_diff'] == 13
    assert kc_season['yards_for'] == 1090
    assert kc_season['turnovers'] == 3
    bal_season = next(r for r in season if r['team_id'] == 'BAL')
    assert bal_season['games_played'] == 2
    assert bal_season['points_for'] == 46


def test_bye_week_yields_no_game_count_for_the_missing_week(
    settings: Settings,
) -> None:
    """Team with a bye (no row in week 5) still sums weeks 1..4 and 6..8,
    games_played counts only populated weeks."""
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 10, 7, 300, 250, 0, 3),
            ('KC', 2024, 2, 'CIN', 14, 10, 280, 240, 0, 3),
            ('KC', 2024, 3, 'ATL', 21, 14, 320, 270, 1, 4),
            ('KC', 2024, 4, 'SF', 17, 13, 290, 260, 0, 2),
            # week 5 bye — no row
            ('KC', 2024, 6, 'GB', 24, 20, 350, 300, 1, 5),
            ('KC', 2024, 7, 'DEN', 28, 14, 380, 230, 0, 3),
        ],
    )
    result = execute_core_team_stats_load(settings, execute=True)
    assert result.row_count == 6
    season = _fetch_season_mart(settings)
    assert len(season) == 1
    kc = season[0]
    assert kc['games_played'] == 6
    assert kc['points_for'] == 10 + 14 + 21 + 17 + 24 + 28
    assert kc['point_diff'] == kc['points_for'] - kc['points_against']


def test_duplicate_team_week_rows_dedupe_by_loaded_at(settings: Settings) -> None:
    """Two stage rows for the same (season, week, team) — latest _loaded_at wins."""
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'team_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                team_id VARCHAR,
                season VARCHAR,
                week VARCHAR,
                opponent_team_id VARCHAR,
                points_for VARCHAR,
                points_against VARCHAR,
                yards_for VARCHAR,
                yards_against VARCHAR,
                turnovers VARCHAR,
                penalties_for VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        # older row
        con.execute(
            f"""INSERT INTO {primary.stage_qualified_table} VALUES (
                'KC','2024','1','BAL','17','20','280','340','3','5',
                'sf-old','nflverse_bulk',TIMESTAMP '2024-09-08 12:00:00'
            )"""
        )
        # corrected row
        con.execute(
            f"""INSERT INTO {primary.stage_qualified_table} VALUES (
                'KC','2024','1','BAL','27','20','380','340','1','5',
                'sf-corrected','nflverse_bulk',TIMESTAMP '2024-09-10 09:00:00'
            )"""
        )
    finally:
        con.close()
    result = execute_core_team_stats_load(settings, execute=True)
    assert result.row_count == 1
    rows = _fetch_core_rows(settings)
    assert len(rows) == 1
    assert rows[0]['points_for'] == 27
    assert rows[0]['turnovers'] == 1


def test_tier_b_disagreement_on_points_for_opens_quarantine(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 27, 20, 380, 340, 1, 5),
        ],
    )
    _seed_tier_b_stage(
        settings,
        [
            # Tier-B disagrees on points_for (24 vs 27).
            ('KC', 2024, 1, 'BAL', 24, 20, 380, 340, 1, 5),
        ],
    )
    result = execute_core_team_stats_load(settings, execute=True)
    assert result.conflict_count == 1
    assert len(result.opened_quarantine_case_ids) == 1
    cases = list_quarantine_cases(settings, status_filter='open')
    assert any(c.scope_ref == 'KC:2024:W01' for c in cases)
    # Tier-A wins in core.team_stats_weekly.
    rows = _fetch_core_rows(settings)
    assert rows[0]['points_for'] == 27


def test_core_load_dispatch_routes_team_stats_slice(settings: Settings) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 27, 20, 380, 340, 1, 5),
        ],
    )
    result = execute_core_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        slice_key='team_stats_weekly',
    )
    assert isinstance(result, CoreTeamStatsLoadResult)
    assert result.qualified_table == CORE_TEAM_STATS_WEEKLY_TABLE
    assert result.mart_qualified_table == MART_TEAM_STATS_WEEKLY_V1
    assert result.season_mart_qualified_table == MART_TEAM_STATS_SEASON_V1


def test_operator_override_resolves_team_stats_quarantine(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 27, 20, 380, 340, 1, 5),
        ],
    )
    _seed_tier_b_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 24, 20, 380, 340, 1, 5),
        ],
    )
    result = execute_core_team_stats_load(settings, execute=True)
    case_id = result.opened_quarantine_case_ids[0]
    resolve_quarantine_case(
        settings,
        quarantine_case_id=case_id,
        action='override',
        triggered_by='andreas',
        note='Tier-A value wins; Tier-B feed known to lag',
    )
    cases = list_quarantine_cases(settings, status_filter='open')
    assert not any(c.quarantine_case_id == case_id for c in cases)


def test_core_team_stats_result_satisfies_core_load_protocol(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('KC', 2024, 1, 'BAL', 27, 20, 380, 340, 1, 5),
        ],
    )
    result = execute_core_team_stats_load(settings, execute=True)
    assert isinstance(result, CoreLoadResultLike)
    for attr in (
        'run_mode', 'run_status', 'pipeline_name', 'ingest_run_id',
        'qualified_table', 'source_row_count', 'row_count',
        'invalid_row_count', 'load_event_id', 'mart_qualified_table',
        'mart_row_count',
    ):
        assert hasattr(result, attr), f'missing {attr}'
