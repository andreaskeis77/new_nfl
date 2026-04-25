"""T3.1S — column-alias registry and per-slice schema-drift handling.

Two layers of test coverage:

1. ``apply_column_aliases`` is exercised directly against synthetic stage
   tables to verify rename, idempotency, missing-table tolerance and
   no-op behaviour for unregistered slices.
2. The three core loaders affected by the nflverse schema drift
   (``players``, ``rosters``, ``team_stats_weekly``) are run end-to-end
   against stage tables that carry the upstream column names
   (``gsis_id``, ``team``); the loader must rename in place and complete
   the core-load gate without modification.

These tests do not exercise the network — see
``tests/test_slices_network_smoke.py`` for the live-URL counterpart that
T3.1S introduces alongside the alias work.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.column_aliases import (
    ALIAS_REGISTRY,
    apply_column_aliases,
    get_aliases_for_slice,
)
from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.players import CORE_PLAYER_TABLE, execute_core_player_load
from new_nfl.core.rosters import CORE_ROSTER_TABLE, execute_core_roster_load
from new_nfl.core.team_stats import (
    CORE_TEAM_STATS_WEEKLY_TABLE,
    execute_core_team_stats_load,
)
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


def _columns(con: duckdb.DuckDBPyConnection, qualified_table: str) -> list[str]:
    return [
        str(row[0]).strip()
        for row in con.execute(f'DESCRIBE {qualified_table}').fetchall()
    ]


# ---------------------------------------------------------------------------
# Registry surface
# ---------------------------------------------------------------------------


def test_alias_registry_covers_three_drifted_primary_slices() -> None:
    # The T3.1S finding: exactly three primary slices drifted on the
    # 2026-04-24 nflverse refresh. Pin the registry shape so that future
    # additions force a deliberate test edit.
    assert set(ALIAS_REGISTRY) == {'players', 'rosters', 'team_stats_weekly'}
    assert ALIAS_REGISTRY['players'] == {'gsis_id': 'player_id'}
    assert ALIAS_REGISTRY['rosters'] == {
        'gsis_id': 'player_id',
        'team': 'team_id',
    }
    assert ALIAS_REGISTRY['team_stats_weekly'] == {'team': 'team_id'}


def test_get_aliases_for_slice_returns_copy_for_unknown_key() -> None:
    assert get_aliases_for_slice('teams') == {}
    assert get_aliases_for_slice('unknown') == {}
    # Returned dict is a copy — caller mutations must not leak into the
    # registry.
    aliases = get_aliases_for_slice('players')
    aliases['extra'] = 'x'
    assert ALIAS_REGISTRY['players'] == {'gsis_id': 'player_id'}


# ---------------------------------------------------------------------------
# apply_column_aliases — direct
# ---------------------------------------------------------------------------


def test_apply_column_aliases_renames_known_column(settings: Settings) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            'CREATE OR REPLACE TABLE stg.t (gsis_id VARCHAR, display_name VARCHAR)'
        )
        applied = apply_column_aliases(con, 'stg.t', 'players')
        assert applied == {'gsis_id': 'player_id'}
        assert _columns(con, 'stg.t') == ['player_id', 'display_name']
    finally:
        con.close()


def test_apply_column_aliases_renames_two_columns_for_rosters(
    settings: Settings,
) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            'CREATE OR REPLACE TABLE stg.t '
            '(gsis_id VARCHAR, team VARCHAR, season VARCHAR, week VARCHAR)'
        )
        applied = apply_column_aliases(con, 'stg.t', 'rosters')
        assert applied == {'gsis_id': 'player_id', 'team': 'team_id'}
        cols = _columns(con, 'stg.t')
        assert 'player_id' in cols
        assert 'team_id' in cols
        assert 'gsis_id' not in cols
        assert 'team' not in cols
    finally:
        con.close()


def test_apply_column_aliases_is_idempotent(settings: Settings) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            'CREATE OR REPLACE TABLE stg.t '
            '(gsis_id VARCHAR, team VARCHAR, season VARCHAR, week VARCHAR)'
        )
        first = apply_column_aliases(con, 'stg.t', 'rosters')
        second = apply_column_aliases(con, 'stg.t', 'rosters')
        assert first == {'gsis_id': 'player_id', 'team': 'team_id'}
        # Second pass observes the canonical names already in place.
        assert second == {}
    finally:
        con.close()


def test_apply_column_aliases_skips_when_canonical_already_present(
    settings: Settings,
) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        # Pathological table that carries both names. The helper must not
        # attempt the rename — DuckDB would otherwise fail with a duplicate
        # column error and corrupt the loader path.
        con.execute(
            'CREATE OR REPLACE TABLE stg.t '
            '(gsis_id VARCHAR, player_id VARCHAR)'
        )
        applied = apply_column_aliases(con, 'stg.t', 'players')
        assert applied == {}
        assert set(_columns(con, 'stg.t')) == {'gsis_id', 'player_id'}
    finally:
        con.close()


def test_apply_column_aliases_unknown_slice_is_noop(settings: Settings) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            'CREATE OR REPLACE TABLE stg.t (player_id VARCHAR, team_id VARCHAR)'
        )
        assert apply_column_aliases(con, 'stg.t', 'teams') == {}
        assert apply_column_aliases(con, 'stg.t', 'games') == {}
        assert apply_column_aliases(con, 'stg.t', 'unknown_slice') == {}
        assert _columns(con, 'stg.t') == ['player_id', 'team_id']
    finally:
        con.close()


def test_apply_column_aliases_missing_table_is_noop(settings: Settings) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        # No CREATE: the cross-check stage may not yet exist on a fresh DB.
        # The helper must absorb the DuckDB error rather than propagate it.
        assert apply_column_aliases(con, 'stg.does_not_exist', 'players') == {}
    finally:
        con.close()


def test_apply_column_aliases_is_case_insensitive(settings: Settings) -> None:
    _bootstrap(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        # DuckDB stores the original case but resolves identifiers case-
        # insensitively. The helper must rename a mixed-case upstream
        # column to the lower-case canonical name.
        con.execute('CREATE OR REPLACE TABLE stg.t ("GSIS_ID" VARCHAR)')
        applied = apply_column_aliases(con, 'stg.t', 'players')
        assert applied == {'gsis_id': 'player_id'}
        assert [c.lower() for c in _columns(con, 'stg.t')] == ['player_id']
    finally:
        con.close()


# ---------------------------------------------------------------------------
# End-to-end: core loaders survive the nflverse upstream rename
# ---------------------------------------------------------------------------


def _seed_players_stage_with_nflverse_schema(settings: Settings) -> None:
    """Seed the Tier-A players stage as nflverse delivers it post-2026-04-24.

    Schema mirrors ``players.csv`` from the
    ``nflverse-data/releases/players`` release after the upstream rename:
    ``gsis_id`` instead of ``player_id``. All other canonical columns are
    present so the dedupe and mart-build paths can run.
    """
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'players')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                gsis_id VARCHAR,
                display_name VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                birth_date VARCHAR,
                position VARCHAR,
                height VARCHAR,
                weight VARCHAR,
                college_name VARCHAR,
                rookie_season VARCHAR,
                last_season VARCHAR,
                current_team_id VARCHAR,
                jersey_number VARCHAR,
                draft_club VARCHAR,
                draft_year VARCHAR,
                draft_round VARCHAR,
                draft_pick VARCHAR,
                status VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        rows = [
            (
                '00-0033873', 'Patrick Mahomes', 'Patrick', 'Mahomes',
                '1995-09-17', 'QB', '75', '230', 'Texas Tech', '2017', '',
                'KC', '15', 'KC', '2017', '1', '10', 'ACT',
            ),
            (
                '00-0019596', 'Tom Brady', 'Tom', 'Brady', '1977-08-03',
                'QB', '76', '225', 'Michigan', '2000', '2022',
                'TB', '12', 'NE', '2000', '6', '199', 'RET',
            ),
        ]
        for row in rows:
            con.execute(
                f'INSERT INTO {primary.stage_qualified_table} VALUES ('
                + ', '.join(['?'] * 18)
                + ", 'sf-players-nflverse-1', ?, CURRENT_TIMESTAMP)",
                [*row, primary.adapter_id],
            )
    finally:
        con.close()


def test_core_player_load_accepts_nflverse_gsis_id_schema(settings: Settings) -> None:
    _seed_players_stage_with_nflverse_schema(settings)

    result = execute_core_player_load(settings, execute=True)

    assert result.run_status == 'core_player_loaded'
    assert result.qualified_table == CORE_PLAYER_TABLE
    assert result.row_count == 2
    assert result.invalid_row_count == 0

    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _columns(con, 'stg.nflverse_bulk_players')
        assert 'player_id' in cols
        assert 'gsis_id' not in cols

        ids = sorted(
            row[0]
            for row in con.execute(
                f'SELECT player_id FROM {CORE_PLAYER_TABLE} ORDER BY player_id'
            ).fetchall()
        )
        assert ids == ['00-0019596', '00-0033873']
    finally:
        con.close()


def _seed_rosters_stage_with_nflverse_schema(settings: Settings) -> None:
    """Seed the Tier-A rosters stage as nflverse delivers it post-2026-04-24.

    Mirrors ``roster_weekly_{season}.csv`` after the upstream rename:
    ``gsis_id`` and ``team`` replace ``player_id`` and ``team_id``.
    """
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'rosters')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                gsis_id VARCHAR,
                team VARCHAR,
                season VARCHAR,
                week VARCHAR,
                position VARCHAR,
                jersey_number VARCHAR,
                status VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        # Two players, two consecutive weeks per player; two distinct teams
        # for player A so the trade-derivation path also exercises the
        # alias rename.
        rows = [
            ('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 2, 'QB', 15, 'active'),
            ('00-0023459', 'NYJ', 2024, 1, 'QB', 8, 'active'),
            ('00-0023459', 'NYJ', 2024, 2, 'QB', 8, 'active'),
        ]
        for player_id, team_id, season, week, position, jersey, status in rows:
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'sf-rosters-nflverse-1', ?,
                    CURRENT_TIMESTAMP
                )
                """,
                [
                    player_id, team_id, str(season), str(week),
                    position, str(jersey), status,
                    primary.adapter_id,
                ],
            )
    finally:
        con.close()


def test_core_roster_load_accepts_nflverse_gsis_id_and_team_schema(
    settings: Settings,
) -> None:
    _seed_rosters_stage_with_nflverse_schema(settings)

    result = execute_core_roster_load(settings, execute=True)

    assert result.run_status == 'core_roster_loaded'
    assert result.qualified_table == CORE_ROSTER_TABLE
    assert result.invalid_row_count == 0
    assert result.interval_count == 2  # one per player
    assert result.open_interval_count == 2

    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _columns(con, 'stg.nflverse_bulk_rosters')
        assert 'player_id' in cols
        assert 'team_id' in cols
        assert 'gsis_id' not in cols
        assert 'team' not in cols

        rows = con.execute(
            f"""
            SELECT player_id, team_id, season, valid_from_week, valid_to_week
            FROM {CORE_ROSTER_TABLE}
            ORDER BY player_id
            """
        ).fetchall()
        assert rows == [
            ('00-0023459', 'NYJ', 2024, 1, None),
            ('00-0033873', 'KC', 2024, 1, None),
        ]
    finally:
        con.close()


def _seed_team_stats_stage_with_nflverse_schema(settings: Settings) -> None:
    """Seed the Tier-A team-stats stage as nflverse delivers it post-2026-04-24.

    Mirrors ``stats_team_week_{season}.csv`` after the upstream rename:
    ``team`` replaces ``team_id``.
    """
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'team_stats_weekly')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                team VARCHAR,
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
        rows = [
            ('KC', 2024, 1, 'BAL', 27, 20, 350, 300, 1, 5),
            ('KC', 2024, 2, 'CIN', 26, 25, 360, 320, 0, 4),
            ('BAL', 2024, 1, 'KC', 20, 27, 280, 350, 2, 6),
        ]
        for team_id, season, week, opp, pf, pa, yf, ya, to, pen in rows:
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'sf-ts-nflverse-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [
                    team_id, str(season), str(week), opp,
                    str(pf), str(pa), str(yf), str(ya), str(to), str(pen),
                    primary.adapter_id,
                ],
            )
    finally:
        con.close()


def test_core_team_stats_load_accepts_nflverse_team_schema(
    settings: Settings,
) -> None:
    _seed_team_stats_stage_with_nflverse_schema(settings)

    result = execute_core_team_stats_load(settings, execute=True)

    assert result.run_status == 'core_team_stats_weekly_loaded'
    assert result.qualified_table == CORE_TEAM_STATS_WEEKLY_TABLE
    assert result.row_count == 3
    assert result.invalid_row_count == 0

    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _columns(con, 'stg.nflverse_bulk_team_stats_weekly')
        assert 'team_id' in cols
        assert 'team' not in cols

        rows = con.execute(
            f"""
            SELECT team_id, season, week, points_for
            FROM {CORE_TEAM_STATS_WEEKLY_TABLE}
            ORDER BY team_id, week
            """
        ).fetchall()
        assert rows == [
            ('BAL', 2024, 1, 20),
            ('KC', 2024, 1, 27),
            ('KC', 2024, 2, 26),
        ]
    finally:
        con.close()
