"""T2.5D Rosters domain — bitemporal core promotion (ADR-0032), Trade /
Release / Signed event derivation, Tier-A vs Tier-B weekly conflict
surface, mart separation between current and history."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.result import CoreLoadResultLike
from new_nfl.core.rosters import (
    CORE_ROSTER_TABLE,
    META_ROSTER_EVENT_TABLE,
    CoreRosterLoadResult,
    execute_core_roster_load,
)
from new_nfl.core_load import execute_core_load
from new_nfl.jobs.quarantine import (
    OPEN_STATUSES,
    list_quarantine_cases,
    resolve_quarantine_case,
)
from new_nfl.mart.roster_current import MART_ROSTER_CURRENT_V1
from new_nfl.mart.roster_history import MART_ROSTER_HISTORY_V1
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


def _seed_tier_a_stage(
    settings: Settings,
    rows: list[tuple[str, str, int, int, str, str | int | None, str]],
) -> None:
    """Seed weekly roster snapshots as Tier-A.

    Row shape: (player_id, team_id, season, week, position, jersey_number,
    status).
    """
    _bootstrap(settings)
    primary = get_slice('nflverse_bulk', 'rosters')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                player_id VARCHAR,
                team_id VARCHAR,
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
        for row in rows:
            player_id, team_id, season, week, position, jersey, status = row
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'sf-rosters-a-1', ?,
                    CURRENT_TIMESTAMP
                )
                """,
                [
                    player_id,
                    team_id,
                    str(season),
                    str(week),
                    position,
                    '' if jersey is None else str(jersey),
                    status,
                    primary.adapter_id,
                ],
            )
    finally:
        con.close()


def _seed_tier_b_stage(
    settings: Settings,
    rows: list[tuple[str, str, int, int, str, str | int | None, str]],
) -> None:
    cross = get_slice('official_context_web', 'rosters')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {cross.stage_qualified_table} (
                player_id VARCHAR,
                team_id VARCHAR,
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
        for row in rows:
            player_id, team_id, season, week, position, jersey, status = row
            con.execute(
                f"""
                INSERT INTO {cross.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'sf-rosters-b-1', ?,
                    CURRENT_TIMESTAMP
                )
                """,
                [
                    player_id,
                    team_id,
                    str(season),
                    str(week),
                    position,
                    '' if jersey is None else str(jersey),
                    status,
                    cross.adapter_id,
                ],
            )
    finally:
        con.close()


def _fetch_intervals(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT player_id, team_id, season, valid_from_week, valid_to_week,
                   position, jersey_number, status
            FROM {CORE_ROSTER_TABLE}
            ORDER BY player_id, season, valid_from_week, team_id
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'player_id', 'team_id', 'season', 'valid_from_week', 'valid_to_week',
        'position', 'jersey_number', 'status',
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _fetch_events(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT event_kind, season, week, player_id, from_team_id, to_team_id
            FROM {META_ROSTER_EVENT_TABLE}
            ORDER BY player_id, season, week, event_kind
            """
        ).fetchall()
    finally:
        con.close()
    keys = ('event_kind', 'season', 'week', 'player_id', 'from_team_id', 'to_team_id')
    return [dict(zip(keys, row, strict=True)) for row in rows]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_core_roster_dry_run_profiles_stage_without_writing(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 2, 'QB', 15, 'active'),
            ('00-0000001', '', 2024, 1, 'QB', 0, 'active'),  # invalid team_id
        ],
    )

    result = execute_core_roster_load(settings, execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_roster_load'
    assert result.qualified_table == CORE_ROSTER_TABLE
    assert result.source_row_count == 3
    assert result.distinct_player_count == 2
    assert result.invalid_row_count == 1
    assert result.row_count == 0
    assert result.interval_count == 0
    con = duckdb.connect(str(settings.db_path))
    try:
        exists = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'core' AND table_name = 'roster_membership'
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert exists == 0


def test_core_roster_execute_builds_intervals_and_both_marts(
    settings: Settings,
) -> None:
    # Single player, contiguous weeks 1..4 on KC → one open interval.
    # Second player, weeks 1..3 on BUF, all tied to the same season max (3).
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 2, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 3, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 4, 'QB', 15, 'active'),
            ('00-0034796', 'BUF', 2024, 1, 'QB', 17, 'active'),
            ('00-0034796', 'BUF', 2024, 2, 'QB', 17, 'active'),
            ('00-0034796', 'BUF', 2024, 3, 'QB', 17, 'active'),
            ('00-0034796', 'BUF', 2024, 4, 'QB', 17, 'active'),
        ],
    )

    result = execute_core_roster_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.run_status == 'core_roster_loaded'
    assert result.row_count == 2
    assert result.interval_count == 2
    assert result.open_interval_count == 2
    assert result.conflict_count == 0
    assert result.event_count == 0  # no transitions
    assert result.mart_qualified_table == MART_ROSTER_CURRENT_V1
    assert result.mart_row_count == 2
    assert result.history_qualified_table == MART_ROSTER_HISTORY_V1
    assert result.history_row_count == 2

    intervals = _fetch_intervals(settings)
    assert len(intervals) == 2
    for row in intervals:
        assert row['valid_from_week'] == 1
        assert row['valid_to_week'] is None  # open
        assert row['position'] == 'QB'
        assert row['status'] == 'active'


def test_trade_detection_emits_trade_event_when_weeks_are_adjacent(
    settings: Settings,
) -> None:
    # Player on KC weeks 1..4, then LV weeks 5..9. Feed also has a second
    # player (anchor) who stays on BUF weeks 1..9 so season global_max=9.
    rows: list[tuple[str, str, int, int, str, int, str]] = []
    for wk in range(1, 5):
        rows.append(('00-0033873', 'KC', 2024, wk, 'QB', 15, 'active'))
    for wk in range(5, 10):
        rows.append(('00-0033873', 'LV', 2024, wk, 'QB', 4, 'active'))
    for wk in range(1, 10):
        rows.append(('00-0034796', 'BUF', 2024, wk, 'QB', 17, 'active'))
    _seed_tier_a_stage(settings, rows)

    result = execute_core_roster_load(settings, execute=True)

    assert result.interval_count == 3
    # Two open intervals (week 9 is the season max): LV and BUF.
    assert result.open_interval_count == 2
    assert result.trade_event_count == 1

    events = _fetch_events(settings)
    trade_events = [e for e in events if e['event_kind'] == 'trade']
    assert len(trade_events) == 1
    t = trade_events[0]
    assert t['player_id'] == '00-0033873'
    assert t['from_team_id'] == 'KC'
    assert t['to_team_id'] == 'LV'
    assert t['week'] == 5


def test_gap_between_teams_emits_released_plus_signed_instead_of_trade(
    settings: Settings,
) -> None:
    # Player on KC weeks 1..3, then absent, then LV weeks 6..9.
    # Anchor on BUF weeks 1..9 guarantees season global_max=9.
    rows: list[tuple[str, str, int, int, str, int, str]] = []
    for wk in range(1, 4):
        rows.append(('00-0033873', 'KC', 2024, wk, 'QB', 15, 'active'))
    for wk in range(6, 10):
        rows.append(('00-0033873', 'LV', 2024, wk, 'QB', 4, 'active'))
    for wk in range(1, 10):
        rows.append(('00-0034796', 'BUF', 2024, wk, 'QB', 17, 'active'))
    _seed_tier_a_stage(settings, rows)

    result = execute_core_roster_load(settings, execute=True)

    assert result.interval_count == 3
    assert result.trade_event_count == 0
    events = _fetch_events(settings)
    kinds_for_player = sorted(
        e['event_kind'] for e in events if e['player_id'] == '00-0033873'
    )
    assert kinds_for_player == ['released', 'signed']
    released = next(
        e for e in events
        if e['player_id'] == '00-0033873' and e['event_kind'] == 'released'
    )
    signed = next(
        e for e in events
        if e['player_id'] == '00-0033873' and e['event_kind'] == 'signed'
    )
    assert released['from_team_id'] == 'KC'
    assert released['to_team_id'] is None
    assert released['week'] == 4  # valid_to (3) + 1
    assert signed['from_team_id'] is None
    assert signed['to_team_id'] == 'LV'
    assert signed['week'] == 6


def test_tier_b_disagreement_on_position_opens_quarantine(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 2, 'QB', 15, 'active'),
            ('00-0034796', 'BUF', 2024, 1, 'QB', 17, 'active'),
            ('00-0034796', 'BUF', 2024, 2, 'QB', 17, 'active'),
        ],
    )
    # Tier-B agrees on Mahomes but disagrees on Allen's position in week 2.
    _seed_tier_b_stage(
        settings,
        [
            ('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 2, 'QB', 15, 'active'),
            ('00-0034796', 'BUF', 2024, 1, 'QB', 17, 'active'),
            ('00-0034796', 'BUF', 2024, 2, 'WR', 17, 'active'),
        ],
    )

    result = execute_core_roster_load(settings, execute=True)

    assert result.conflict_count == 1
    assert len(result.opened_quarantine_case_ids) == 1

    # Tier-A value must win in core.roster_membership.
    intervals = _fetch_intervals(settings)
    allen_intervals = [r for r in intervals if r['player_id'] == '00-0034796']
    # Allen should remain a single QB interval (week-2 conflict doesn't split
    # the interval because Tier-A is the truth).
    assert len(allen_intervals) == 1
    assert allen_intervals[0]['position'] == 'QB'

    cases = list_quarantine_cases(settings, status_filter='open')
    assert len(cases) == 1
    case = cases[0]
    assert case.scope_type == 'roster_membership'
    assert case.reason_code == 'tier_b_disagreement'
    assert case.status in OPEN_STATUSES
    assert case.scope_ref.startswith('00-0034796:BUF:2024:W02')


def test_core_load_dispatch_routes_rosters_slice(settings: Settings) -> None:
    _seed_tier_a_stage(
        settings,
        [
            ('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active'),
            ('00-0033873', 'KC', 2024, 2, 'QB', 15, 'active'),
        ],
    )

    result = execute_core_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        slice_key='rosters',
    )

    assert isinstance(result, CoreRosterLoadResult)
    assert result.qualified_table == CORE_ROSTER_TABLE
    assert result.row_count == 1


def test_operator_override_resolves_roster_quarantine(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [('00-0034796', 'BUF', 2024, 1, 'QB', 17, 'active')],
    )
    _seed_tier_b_stage(
        settings,
        [('00-0034796', 'BUF', 2024, 1, 'WR', 17, 'active')],
    )
    result = execute_core_roster_load(settings, execute=True)
    assert len(result.opened_quarantine_case_ids) == 1
    case_id = result.opened_quarantine_case_ids[0]

    override = resolve_quarantine_case(
        settings,
        quarantine_case_id=case_id,
        action='override',
        note='operator confirms Tier-A position in T2.5D smoke-run',
    )

    assert override['case'].status == 'resolved'
    open_cases = list_quarantine_cases(settings, status_filter='open')
    assert case_id not in {c.quarantine_case_id for c in open_cases}


def test_roster_current_only_shows_open_intervals(settings: Settings) -> None:
    # Player on KC weeks 1..3 (closed after trade), LV weeks 4..9 (open).
    rows: list[tuple[str, str, int, int, str, int, str]] = []
    for wk in range(1, 4):
        rows.append(('00-0033873', 'KC', 2024, wk, 'QB', 15, 'active'))
    for wk in range(4, 10):
        rows.append(('00-0033873', 'LV', 2024, wk, 'QB', 4, 'active'))
    for wk in range(1, 10):
        rows.append(('00-0034796', 'BUF', 2024, wk, 'QB', 17, 'active'))
    _seed_tier_a_stage(settings, rows)

    execute_core_roster_load(settings, execute=True)

    con = duckdb.connect(str(settings.db_path))
    try:
        current_rows = con.execute(
            f"""
            SELECT player_id, team_id, valid_from_week, valid_to_week
            FROM {MART_ROSTER_CURRENT_V1}
            ORDER BY player_id, team_id
            """
        ).fetchall()
    finally:
        con.close()

    assert len(current_rows) == 2
    teams_per_player = {r[0]: r[1] for r in current_rows}
    assert teams_per_player == {'00-0033873': 'LV', '00-0034796': 'BUF'}
    for _, _, _, valid_to in current_rows:
        assert valid_to is None


def test_roster_history_shows_full_interval_timeline(settings: Settings) -> None:
    rows: list[tuple[str, str, int, int, str, int, str]] = []
    for wk in range(1, 4):
        rows.append(('00-0033873', 'KC', 2024, wk, 'QB', 15, 'active'))
    for wk in range(4, 10):
        rows.append(('00-0033873', 'LV', 2024, wk, 'QB', 4, 'active'))
    for wk in range(1, 10):
        rows.append(('00-0034796', 'BUF', 2024, wk, 'QB', 17, 'active'))
    _seed_tier_a_stage(settings, rows)

    execute_core_roster_load(settings, execute=True)

    con = duckdb.connect(str(settings.db_path))
    try:
        history_rows = con.execute(
            f"""
            SELECT player_id, team_id, valid_from_week, valid_to_week,
                   is_open, jersey_number
            FROM {MART_ROSTER_HISTORY_V1}
            ORDER BY player_id, valid_from_week, team_id
            """
        ).fetchall()
    finally:
        con.close()

    assert len(history_rows) == 3
    mahomes_rows = [r for r in history_rows if r[0] == '00-0033873']
    assert len(mahomes_rows) == 2
    # First interval: KC, weeks 1..3, closed.
    assert mahomes_rows[0][1] == 'KC'
    assert mahomes_rows[0][2] == 1
    assert mahomes_rows[0][3] == 3
    assert mahomes_rows[0][4] is False
    # Second interval: LV, weeks 4..NULL, open.
    assert mahomes_rows[1][1] == 'LV'
    assert mahomes_rows[1][2] == 4
    assert mahomes_rows[1][3] is None
    assert mahomes_rows[1][4] is True


def test_core_roster_result_satisfies_core_load_protocol(
    settings: Settings,
) -> None:
    _seed_tier_a_stage(
        settings,
        [('00-0033873', 'KC', 2024, 1, 'QB', 15, 'active')],
    )

    result = execute_core_roster_load(settings, execute=True)

    # Runtime-checkable Protocol round-trip: every attribute the CLI's
    # print_common_core_load_lines relies on must be present and correctly
    # typed.
    assert isinstance(result, CoreLoadResultLike)
    assert isinstance(result.run_mode, str)
    assert isinstance(result.run_status, str)
    assert isinstance(result.pipeline_name, str)
    assert isinstance(result.ingest_run_id, str)
    assert isinstance(result.qualified_table, str)
    assert isinstance(result.source_row_count, int)
    assert isinstance(result.row_count, int)
    assert isinstance(result.invalid_row_count, int)
    assert isinstance(result.load_event_id, str)
    assert isinstance(result.mart_qualified_table, str)
    assert isinstance(result.mart_row_count, int)
    # Slice-specific extras still reachable on the concrete dataclass.
    assert result.trade_event_count == 0
    assert result.event_count == 0
    assert result.open_interval_count == 1
    assert result.history_qualified_table == MART_ROSTER_HISTORY_V1
