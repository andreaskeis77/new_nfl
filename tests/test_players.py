"""T2.5C Players domain — core promotion, mart build, Tier-A vs Tier-B
conflict, real HTTP round-trip, plus the first real dedupe application
driven against a freshly promoted ``core.player``."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.remote_fetch import execute_remote_fetch
from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.players import CORE_PLAYER_TABLE, execute_core_player_load
from new_nfl.core_load import execute_core_load
from new_nfl.dedupe import run_player_dedupe_from_core
from new_nfl.jobs.quarantine import (
    OPEN_STATUSES,
    list_quarantine_cases,
    resolve_quarantine_case,
)
from new_nfl.mart.player_overview import MART_PLAYER_OVERVIEW_V1
from new_nfl.metadata import seed_default_sources
from new_nfl.settings import Settings
from new_nfl.stage_load import execute_stage_load


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


# Tier-A fixture: five players covering (a) complete record with every
# canonical field, (b) minimal record with many NULLs, (c) retired player
# (last_season populated — is_active must resolve FALSE), (d) active player
# (last_season NULL — is_active TRUE) and (e) a second canonical player_id
# that shares the display name of (a) so the downstream dedupe pipeline has
# a realistic same-name / same-birth-year cluster candidate.
_TIER_A_ROWS: tuple[tuple, ...] = (
    # player_id, display_name, first_name, last_name, birth_date, position,
    # height, weight, college_name, rookie_season, last_season,
    # current_team_id, jersey_number, draft_club, draft_year, draft_round,
    # draft_pick, status
    (
        '00-0033873', 'Patrick Mahomes', 'Patrick', 'Mahomes', '1995-09-17',
        'QB', '75', '230', 'Texas Tech', '2017', '',
        'KC', '15', 'KC', '2017', '1', '10', 'ACT',
    ),
    (
        '00-0036355', 'Minimal Player', '', '', '',
        '', '', '', '', '', '',
        '', '', '', '', '', '', '',
    ),
    (
        '00-0019596', 'Tom Brady', 'Tom', 'Brady', '1977-08-03',
        'QB', '76', '225', 'Michigan', '2000', '2022',
        'TB', '12', 'NE', '2000', '6', '199', 'RET',
    ),
    (
        '00-0023459', 'Aaron Rodgers', 'Aaron', 'Rodgers', '1983-12-02',
        'QB', '74', '225', 'California', '2005', '',
        'NYJ', '8', 'GB', '2005', '1', '24', 'ACT',
    ),
    # Same display_name + birth_date as (a) but a different canonical
    # player_id — drives the dedupe-from-core cluster test below.
    (
        '00-0099999', 'Patrick Mahomes', 'Patrick', 'Mahomes', '1995-09-17',
        'QB', '75', '230', 'Texas Tech', '2017', '',
        'KC', '15', 'KC', '2017', '1', '10', 'ACT',
    ),
)


def _seed_tier_a_stage(settings: Settings, rows: tuple[tuple, ...]) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    primary = get_slice('nflverse_bulk', 'players')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                player_id VARCHAR,
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
        for row in rows:
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, CURRENT_TIMESTAMP
                )
                """,
                [*row, 'sf-players-a-1', primary.adapter_id],
            )
    finally:
        con.close()


def _seed_tier_b_stage(
    settings: Settings,
    rows: list[tuple[str, str, str, str, str]],
) -> None:
    """Seed (player_id, display_name, position, current_team_id, jersey_number)
    into the Tier-B cross-check stage."""
    cross = get_slice('official_context_web', 'players')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {cross.stage_qualified_table} (
                player_id VARCHAR,
                display_name VARCHAR,
                position VARCHAR,
                current_team_id VARCHAR,
                jersey_number VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        for row in rows:
            con.execute(
                f"""
                INSERT INTO {cross.stage_qualified_table} VALUES (
                    ?, ?, ?, ?, ?, 'sf-players-b-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [*row, cross.adapter_id],
            )
    finally:
        con.close()


def _core_player_rows(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT player_id, display_name, position, current_team_id,
                   jersey_number, birth_date, rookie_season, last_season,
                   draft_year, draft_pick, status
            FROM {CORE_PLAYER_TABLE}
            ORDER BY player_id
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'player_id', 'display_name', 'position', 'current_team_id',
        'jersey_number', 'birth_date', 'rookie_season', 'last_season',
        'draft_year', 'draft_pick', 'status',
    )
    return [dict(zip(keys, row)) for row in rows]


def test_core_player_dry_run_profiles_stage_without_writing(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_player_load(settings, execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_player_load'
    assert result.qualified_table == CORE_PLAYER_TABLE
    assert result.source_row_count == 5
    assert result.distinct_player_count == 5
    assert result.invalid_row_count == 0
    assert result.row_count == 0
    con = duckdb.connect(str(settings.db_path))
    try:
        exists = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'core' AND table_name = 'player'
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert exists == 0


def test_core_player_execute_rebuilds_core_and_mart(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_player_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.run_status == 'core_player_loaded'
    assert result.row_count == 5
    assert result.conflict_count == 0
    assert result.opened_quarantine_case_ids == ()
    assert result.mart_qualified_table == MART_PLAYER_OVERVIEW_V1
    assert result.mart_row_count == 5

    rows = {r['player_id']: r for r in _core_player_rows(settings)}
    assert set(rows.keys()) == {
        '00-0019596',
        '00-0023459',
        '00-0033873',
        '00-0036355',
        '00-0099999',
    }
    mahomes = rows['00-0033873']
    assert mahomes['display_name'] == 'Patrick Mahomes'
    assert mahomes['position'] == 'QB'
    assert mahomes['current_team_id'] == 'KC'
    assert mahomes['jersey_number'] == 15
    assert mahomes['draft_year'] == 2017
    assert mahomes['draft_pick'] == 10
    assert mahomes['last_season'] is None

    brady = rows['00-0019596']
    assert brady['last_season'] == 2022
    assert brady['status'] == 'RET'

    minimal = rows['00-0036355']
    assert minimal['display_name'] == 'Minimal Player'
    assert minimal['position'] is None
    assert minimal['current_team_id'] is None
    assert minimal['birth_date'] is None

    con = duckdb.connect(str(settings.db_path))
    try:
        mart_rows = con.execute(
            f"""
            SELECT player_id, display_name, full_name, is_active,
                   player_id_lower, position_lower, current_team_id_lower,
                   position_is_known
            FROM {MART_PLAYER_OVERVIEW_V1}
            ORDER BY player_id
            """
        ).fetchall()
    finally:
        con.close()
    by_player = {r[0]: r for r in mart_rows}
    assert by_player['00-0033873'][2] == 'Patrick Mahomes'
    assert by_player['00-0033873'][3] is True  # Mahomes is active.
    assert by_player['00-0019596'][3] is False  # Brady retired.
    # Lowercased filter columns.
    assert by_player['00-0033873'][4] == '00-0033873'
    assert by_player['00-0033873'][5] == 'qb'
    assert by_player['00-0033873'][6] == 'kc'
    # No ontology loaded in this test → position_is_known must be NULL.
    assert by_player['00-0033873'][7] is None


def test_core_player_tier_b_disagreement_opens_quarantine(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    # Tier-B agrees on Mahomes but disagrees on:
    # - Rodgers jersey_number (claims 12 instead of 8)
    # - Brady current_team_id (claims NE instead of TB)
    _seed_tier_b_stage(
        settings,
        [
            ('00-0033873', 'Patrick Mahomes', 'QB', 'KC', '15'),
            ('00-0023459', 'Aaron Rodgers', 'QB', 'NYJ', '12'),
            ('00-0019596', 'Tom Brady', 'QB', 'NE', '12'),
        ],
    )

    result = execute_core_player_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.conflict_count == 2
    assert len(result.opened_quarantine_case_ids) == 2

    # Tier-A values must win in core.player.
    rows = {r['player_id']: r for r in _core_player_rows(settings)}
    assert rows['00-0023459']['jersey_number'] == 8
    assert rows['00-0019596']['current_team_id'] == 'TB'

    cases = list_quarantine_cases(settings, status_filter='open')
    assert {c.scope_ref for c in cases} == {'00-0023459', '00-0019596'}
    for case in cases:
        assert case.scope_type == 'player'
        assert case.reason_code == 'tier_b_disagreement'
        assert case.status in OPEN_STATUSES


def test_operator_override_resolves_player_quarantine(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    _seed_tier_b_stage(
        settings,
        [('00-0023459', 'Aaron Rodgers', 'QB', 'NYJ', '12')],
    )
    result = execute_core_player_load(settings, execute=True)
    assert len(result.opened_quarantine_case_ids) == 1
    case_id = result.opened_quarantine_case_ids[0]

    override = resolve_quarantine_case(
        settings,
        quarantine_case_id=case_id,
        action='override',
        note='operator confirms Tier-A jersey in T2.5C smoke-run',
    )

    assert override['case'].status == 'resolved'
    open_cases = list_quarantine_cases(settings, status_filter='open')
    assert case_id not in {c.quarantine_case_id for c in open_cases}


def test_core_load_dispatch_routes_players_slice(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        slice_key='players',
    )

    from new_nfl.core.players import CorePlayerLoadResult
    assert isinstance(result, CorePlayerLoadResult)
    assert result.qualified_table == CORE_PLAYER_TABLE
    assert result.row_count == 5


def test_dedupe_from_core_clusters_same_player_across_ids(settings: Settings) -> None:
    """First real dedupe application: two canonical player_ids that refer to
    the same real person (same display_name + birth_year + position) must
    land in the same auto-merge cluster once the pipeline scores the pair."""
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    execute_core_player_load(settings, execute=True)

    result = run_player_dedupe_from_core(settings)

    assert result.domain == 'players'
    assert result.source_ref == 'core.player'
    assert result.input_record_count == 5
    # Mahomes pair must score above the auto-merge upper threshold (0.85).
    assert result.auto_merge_pair_count >= 1
    # Exactly one cluster larger than 1 — the duplicated Mahomes entry.
    multi_clusters = [c for c in result.clusters if len(c.record_ids) > 1]
    assert len(multi_clusters) == 1
    merged = set(multi_clusters[0].record_ids)
    assert merged == {'00-0033873', '00-0099999'}


def test_dedupe_from_core_fails_before_core_player_exists(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    with pytest.raises(ValueError, match='core.player does not exist'):
        run_player_dedupe_from_core(settings)


# ---------------------------------------------------------------------------
# Real HTTP round-trip for the official_context_web players cross-check slice.
# Spins up a stdlib ThreadingHTTPServer on a free port, serves a tiny CSV
# payload, drives execute_remote_fetch + execute_stage_load through the slice
# registry, then promotes Tier-A and asserts the quarantine surface reflects
# the drift introduced by the served Tier-B CSV.
# ---------------------------------------------------------------------------


_TIER_B_CSV = (
    "player_id,display_name,position,current_team_id,jersey_number\n"
    "00-0033873,Patrick Mahomes,QB,KC,15\n"
    "00-0023459,Aaron Rodgers,QB,NYJ,8\n"
)


def _make_handler(payload: bytes):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802  (stdlib signature)
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args, **kwargs) -> None:  # silence test noise
            return

    return _Handler


def test_official_context_web_players_real_http_roundtrip(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    server = ThreadingHTTPServer(
        ('127.0.0.1', 0),
        _make_handler(_TIER_B_CSV.encode('utf-8')),
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{port}/players.csv'

        fetch = execute_remote_fetch(
            settings,
            adapter_id='official_context_web',
            execute=True,
            remote_url_override=url,
            slice_key='players',
        )
        assert fetch.run_status == 'remote_fetched'
        assert fetch.downloaded_bytes == len(_TIER_B_CSV.encode('utf-8'))
        assert Path(fetch.downloaded_file_path).exists()

        stage = execute_stage_load(
            settings,
            adapter_id='official_context_web',
            execute=True,
            source_file_id=None,
            slice_key='players',
        )
        cross = get_slice('official_context_web', 'players')
        assert stage.qualified_table == cross.stage_qualified_table
        assert stage.row_count == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_roundtrip_feeds_tier_b_player_quarantine(settings: Settings) -> None:
    """End-to-end: Tier-A stage + real HTTP Tier-B → quarantine surfaces drift.

    The served CSV reports a different jersey_number for Rodgers than Tier-A,
    so the T2.5C promoter must open exactly one quarantine case after the
    real fetch + stage-load pipeline — no manual stage seeding for Tier-B.
    """
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    divergent_csv = (
        "player_id,display_name,position,current_team_id,jersey_number\n"
        "00-0023459,Aaron Rodgers,QB,NYJ,12\n"
    ).encode('utf-8')
    server = ThreadingHTTPServer(
        ('127.0.0.1', 0),
        _make_handler(divergent_csv),
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{port}/players.csv'
        execute_remote_fetch(
            settings,
            adapter_id='official_context_web',
            execute=True,
            remote_url_override=url,
            slice_key='players',
        )
        execute_stage_load(
            settings,
            adapter_id='official_context_web',
            execute=True,
            source_file_id=None,
            slice_key='players',
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    result = execute_core_player_load(settings, execute=True)
    assert result.conflict_count == 1
    assert len(result.opened_quarantine_case_ids) == 1
    cases = list_quarantine_cases(settings, status_filter='open')
    assert {c.scope_ref for c in cases} == {'00-0023459'}
