"""T2.5A Teams domain — core promotion, mart build, Tier-A vs Tier-B conflict."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.teams import CORE_TEAM_TABLE, execute_core_team_load
from new_nfl.core_load import execute_core_load
from new_nfl.jobs.quarantine import (
    OPEN_STATUSES,
    list_quarantine_cases,
    resolve_quarantine_case,
)
from new_nfl.mart.team_overview import MART_TEAM_OVERVIEW_V1
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


_TIER_A_COLUMNS = (
    'team_id',
    'team_abbr',
    'team_name',
    'team_nick',
    'team_conference',
    'team_division',
    'team_color',
    'team_color2',
    'first_season',
    'last_season',
    'successor_team_id',
)

# (team_id, abbr, name, nick, conf, div, color, color2, first, last, succ)
_TIER_A_ROWS: tuple[tuple, ...] = (
    ('KC', 'KC', 'Kansas City Chiefs', 'Chiefs', 'AFC', 'AFC West',
     '#E31837', '#FFB81C', '1960', None, None),
    ('SF', 'SF', 'San Francisco 49ers', '49ers', 'NFC', 'NFC West',
     '#AA0000', '#B3995D', '1946', None, None),
    ('OAK', 'OAK', 'Oakland Raiders', 'Raiders', 'AFC', 'AFC West',
     '#000000', '#A5ACAF', '1960', '2019', 'LV'),
    ('LV', 'LV', 'Las Vegas Raiders', 'Raiders', 'AFC', 'AFC West',
     '#000000', '#A5ACAF', '2020', None, None),
)


def _seed_tier_a_stage(settings: Settings, rows: tuple[tuple, ...]) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    primary = get_slice('nflverse_bulk', 'teams')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                team_id VARCHAR,
                team_abbr VARCHAR,
                team_name VARCHAR,
                team_nick VARCHAR,
                team_conference VARCHAR,
                team_division VARCHAR,
                team_color VARCHAR,
                team_color2 VARCHAR,
                first_season VARCHAR,
                last_season VARCHAR,
                successor_team_id VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        for row in rows:
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} (
                    team_id, team_abbr, team_name, team_nick,
                    team_conference, team_division, team_color, team_color2,
                    first_season, last_season, successor_team_id,
                    _source_file_id, _adapter_id, _loaded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [*row, 'sf-a-1', primary.adapter_id],
            )
    finally:
        con.close()


def _seed_tier_b_stage(
    settings: Settings,
    rows: list[tuple[str, str, str, str, str]],
) -> None:
    """Seed (team_id, team_abbr, team_name, team_color, team_division)."""
    cross = get_slice('official_context_web', 'teams')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {cross.stage_qualified_table} (
                team_id VARCHAR,
                team_abbr VARCHAR,
                team_name VARCHAR,
                team_color VARCHAR,
                team_division VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        for row in rows:
            con.execute(
                f"""
                INSERT INTO {cross.stage_qualified_table} (
                    team_id, team_abbr, team_name, team_color, team_division,
                    _source_file_id, _adapter_id, _loaded_at
                )
                VALUES (?, ?, ?, ?, ?, 'sf-b-1', ?, CURRENT_TIMESTAMP)
                """,
                [*row, cross.adapter_id],
            )
    finally:
        con.close()


def _core_team_rows(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT team_id, team_abbr, team_name, team_conference,
                   team_division, team_color, first_season, last_season,
                   successor_team_id
            FROM {CORE_TEAM_TABLE}
            ORDER BY team_id
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'team_id', 'team_abbr', 'team_name', 'team_conference',
        'team_division', 'team_color', 'first_season', 'last_season',
        'successor_team_id',
    )
    return [dict(zip(keys, row)) for row in rows]


def test_core_team_dry_run_profiles_stage_without_writing(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_team_load(settings, execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_team_load'
    assert result.qualified_table == CORE_TEAM_TABLE
    assert result.source_row_count == 4
    assert result.distinct_team_count == 4
    assert result.invalid_row_count == 0
    assert result.row_count == 0
    # Core table must not exist yet in dry-run mode.
    con = duckdb.connect(str(settings.db_path))
    try:
        exists = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'core' AND table_name = 'team'
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert exists == 0


def test_core_team_execute_rebuilds_core_and_mart(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_team_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.run_status == 'core_team_loaded'
    assert result.row_count == 4
    assert result.conflict_count == 0
    assert result.opened_quarantine_case_ids == ()
    assert result.mart_qualified_table == MART_TEAM_OVERVIEW_V1
    assert result.mart_row_count == 4

    rows = _core_team_rows(settings)
    assert [r['team_id'] for r in rows] == ['KC', 'LV', 'OAK', 'SF']
    oak = next(r for r in rows if r['team_id'] == 'OAK')
    assert oak['successor_team_id'] == 'LV'
    assert oak['last_season'] == 2019
    lv = next(r for r in rows if r['team_id'] == 'LV')
    assert lv['first_season'] == 2020
    assert lv['last_season'] is None

    con = duckdb.connect(str(settings.db_path))
    try:
        mart_rows = con.execute(
            f"""
            SELECT team_id, is_active, team_abbr_lower, team_name_lower
            FROM {MART_TEAM_OVERVIEW_V1}
            ORDER BY team_id
            """
        ).fetchall()
    finally:
        con.close()
    assert [r[0] for r in mart_rows] == ['KC', 'LV', 'OAK', 'SF']
    active_flags = {r[0]: r[1] for r in mart_rows}
    assert active_flags['OAK'] is False
    assert active_flags['LV'] is True
    assert active_flags['KC'] is True


def test_core_team_tier_b_disagreement_opens_quarantine(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    # Tier-B agrees on KC but disagrees on SF (different name) and KC color.
    _seed_tier_b_stage(
        settings,
        [
            ('KC', 'KC', 'Kansas City Chiefs', '#FF0000', 'AFC West'),
            ('SF', 'SF', 'San Fran 49ers', '#AA0000', 'NFC West'),
        ],
    )

    result = execute_core_team_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.conflict_count == 2  # KC.color, SF.team_name
    assert len(result.opened_quarantine_case_ids) == 2

    # Tier-A values must win in core.team.
    rows = {r['team_id']: r for r in _core_team_rows(settings)}
    assert rows['KC']['team_color'] == '#E31837'
    assert rows['SF']['team_name'] == 'San Francisco 49ers'

    cases = list_quarantine_cases(settings, status_filter='open')
    assert {c.scope_ref for c in cases} == {'KC', 'SF'}
    for case in cases:
        assert case.scope_type == 'team'
        assert case.reason_code == 'tier_b_disagreement'
        assert case.status in OPEN_STATUSES


def test_operator_override_resolves_quarantine(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    _seed_tier_b_stage(
        settings,
        [('KC', 'KC', 'Kansas City Chiefs', '#FF0000', 'AFC West')],
    )
    result = execute_core_team_load(settings, execute=True)
    assert len(result.opened_quarantine_case_ids) == 1
    case_id = result.opened_quarantine_case_ids[0]

    override = resolve_quarantine_case(
        settings,
        quarantine_case_id=case_id,
        action='override',
        note='operator confirms Tier-A color in T2.5A smoke-run',
    )

    assert override['case'].status == 'resolved'
    open_cases = list_quarantine_cases(settings, status_filter='open')
    assert case_id not in {c.quarantine_case_id for c in open_cases}


def test_core_load_dispatch_routes_teams_slice(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        slice_key='teams',
    )

    from new_nfl.core.teams import CoreTeamLoadResult
    assert isinstance(result, CoreTeamLoadResult)
    assert result.qualified_table == CORE_TEAM_TABLE
    assert result.row_count == 4
