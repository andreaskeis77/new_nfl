"""T2.5B Games domain — core promotion, mart build, Tier-A vs Tier-B conflict,
real HTTP round-trip through the official_context_web adapter."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.remote_fetch import execute_remote_fetch
from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.games import CORE_GAME_TABLE, execute_core_game_load
from new_nfl.core_load import execute_core_load
from new_nfl.jobs.quarantine import (
    OPEN_STATUSES,
    list_quarantine_cases,
    resolve_quarantine_case,
)
from new_nfl.mart.game_overview import MART_GAME_OVERVIEW_V1
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


# Tier-A fixture: four games covering (a) completed with clear winner,
# (b) completed with OT and result column, (c) tie, (d) future/scheduled.
_TIER_A_ROWS: tuple[tuple, ...] = (
    # game_id, season, game_type, week, gameday, weekday, gametime,
    # home_team, away_team, home_score, away_score, result, overtime,
    # stadium, roof, surface
    ('2024_01_DET_KC', '2024', 'REG', '1', '2024-09-05', 'Thu', '20:20',
     'KC', 'DET', '21', '24', '-3', '0',
     'GEHA Field at Arrowhead Stadium', 'outdoors', 'grass'),
    ('2024_01_SF_NYJ', '2024', 'REG', '1', '2024-09-09', 'Mon', '20:15',
     'SF', 'NYJ', '32', '19', '13', '1',
     "Levi's Stadium", 'outdoors', 'grass'),
    ('2024_02_LV_BAL', '2024', 'REG', '2', '2024-09-15', 'Sun', '13:00',
     'BAL', 'LV', '23', '23', '0', '1',
     'M&T Bank Stadium', 'outdoors', 'astroturf'),
    ('2024_18_KC_DEN', '2024', 'REG', '18', '2025-01-05', 'Sun', '16:25',
     'DEN', 'KC', None, None, None, '0',
     'Empower Field at Mile High', 'outdoors', 'grass'),
)


def _seed_tier_a_stage(settings: Settings, rows: tuple[tuple, ...]) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    primary = get_slice('nflverse_bulk', 'games')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                game_id VARCHAR,
                season VARCHAR,
                game_type VARCHAR,
                week VARCHAR,
                gameday VARCHAR,
                weekday VARCHAR,
                gametime VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                home_score VARCHAR,
                away_score VARCHAR,
                result VARCHAR,
                overtime VARCHAR,
                stadium VARCHAR,
                roof VARCHAR,
                surface VARCHAR,
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
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, CURRENT_TIMESTAMP
                )
                """,
                [*row, 'sf-games-a-1', primary.adapter_id],
            )
    finally:
        con.close()


def _seed_tier_b_stage(
    settings: Settings,
    rows: list[tuple[str, str, str, str]],
) -> None:
    """Seed (game_id, home_score, away_score, stadium) into Tier-B stage."""
    cross = get_slice('official_context_web', 'games')
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {cross.stage_qualified_table} (
                game_id VARCHAR,
                home_score VARCHAR,
                away_score VARCHAR,
                stadium VARCHAR,
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
                    ?, ?, ?, ?, 'sf-games-b-1', ?, CURRENT_TIMESTAMP
                )
                """,
                [*row, cross.adapter_id],
            )
    finally:
        con.close()


def _core_game_rows(settings: Settings) -> list[dict[str, object]]:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT game_id, season, week, home_team, away_team,
                   home_score, away_score, result, overtime,
                   stadium, roof, surface
            FROM {CORE_GAME_TABLE}
            ORDER BY game_id
            """
        ).fetchall()
    finally:
        con.close()
    keys = (
        'game_id', 'season', 'week', 'home_team', 'away_team',
        'home_score', 'away_score', 'result', 'overtime',
        'stadium', 'roof', 'surface',
    )
    return [dict(zip(keys, row)) for row in rows]


def test_core_game_dry_run_profiles_stage_without_writing(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_game_load(settings, execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_game_load'
    assert result.qualified_table == CORE_GAME_TABLE
    assert result.source_row_count == 4
    assert result.distinct_game_count == 4
    assert result.invalid_row_count == 0
    assert result.row_count == 0
    # Core table must not exist yet in dry-run mode.
    con = duckdb.connect(str(settings.db_path))
    try:
        exists = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'core' AND table_name = 'game'
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert exists == 0


def test_core_game_execute_rebuilds_core_and_mart(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_game_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.run_status == 'core_game_loaded'
    assert result.row_count == 4
    assert result.conflict_count == 0
    assert result.opened_quarantine_case_ids == ()
    assert result.mart_qualified_table == MART_GAME_OVERVIEW_V1
    assert result.mart_row_count == 4

    rows = {r['game_id']: r for r in _core_game_rows(settings)}
    assert set(rows.keys()) == {
        '2024_01_det_kc',
        '2024_01_sf_nyj',
        '2024_02_lv_bal',
        '2024_18_kc_den',
    }
    kc_det = rows['2024_01_det_kc']
    assert kc_det['home_team'] == 'KC'
    assert kc_det['away_team'] == 'DET'
    assert kc_det['home_score'] == 21
    assert kc_det['away_score'] == 24
    assert kc_det['result'] == -3

    future = rows['2024_18_kc_den']
    assert future['home_score'] is None
    assert future['away_score'] is None

    con = duckdb.connect(str(settings.db_path))
    try:
        mart_rows = con.execute(
            f"""
            SELECT game_id, is_completed, winner_team, game_id_lower,
                   home_team_lower, away_team_lower
            FROM {MART_GAME_OVERVIEW_V1}
            ORDER BY game_id
            """
        ).fetchall()
    finally:
        con.close()
    by_game = {r[0]: r for r in mart_rows}
    # Detroit beat KC in Week 1.
    assert by_game['2024_01_det_kc'][1] is True
    assert by_game['2024_01_det_kc'][2] == 'DET'
    # SF vs NYJ: SF wins at home.
    assert by_game['2024_01_sf_nyj'][2] == 'SF'
    # Tie game.
    assert by_game['2024_02_lv_bal'][2] == 'TIE'
    # Future game: still scheduled.
    assert by_game['2024_18_kc_den'][1] is False
    assert by_game['2024_18_kc_den'][2] is None
    # Lowercased filter columns.
    assert by_game['2024_01_det_kc'][3] == '2024_01_det_kc'
    assert by_game['2024_01_det_kc'][4] == 'kc'
    assert by_game['2024_01_det_kc'][5] == 'det'


def test_core_game_tier_b_disagreement_opens_quarantine(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    # Tier-B agrees on DET/KC scores but disagrees on:
    # - SF/NYJ home_score (claims 35 instead of 32)
    # - KC/DEN stadium (claims different name)
    _seed_tier_b_stage(
        settings,
        [
            ('2024_01_det_kc', '21', '24', 'GEHA Field at Arrowhead Stadium'),
            ('2024_01_sf_nyj', '35', '19', "Levi's Stadium"),
            ('2024_18_kc_den', '', '', 'Mile High Stadium'),
        ],
    )

    result = execute_core_game_load(settings, execute=True)

    assert result.run_mode == 'execute'
    assert result.conflict_count == 2  # SF home_score, KC/DEN stadium
    assert len(result.opened_quarantine_case_ids) == 2

    # Tier-A values must win in core.game.
    rows = {r['game_id']: r for r in _core_game_rows(settings)}
    assert rows['2024_01_sf_nyj']['home_score'] == 32
    assert rows['2024_18_kc_den']['stadium'] == 'Empower Field at Mile High'

    cases = list_quarantine_cases(settings, status_filter='open')
    assert {c.scope_ref for c in cases} == {
        '2024_01_sf_nyj',
        '2024_18_kc_den',
    }
    for case in cases:
        assert case.scope_type == 'game'
        assert case.reason_code == 'tier_b_disagreement'
        assert case.status in OPEN_STATUSES


def test_operator_override_resolves_game_quarantine(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)
    _seed_tier_b_stage(
        settings,
        [('2024_01_sf_nyj', '35', '19', "Levi's Stadium")],
    )
    result = execute_core_game_load(settings, execute=True)
    assert len(result.opened_quarantine_case_ids) == 1
    case_id = result.opened_quarantine_case_ids[0]

    override = resolve_quarantine_case(
        settings,
        quarantine_case_id=case_id,
        action='override',
        note='operator confirms Tier-A score in T2.5B smoke-run',
    )

    assert override['case'].status == 'resolved'
    open_cases = list_quarantine_cases(settings, status_filter='open')
    assert case_id not in {c.quarantine_case_id for c in open_cases}


def test_core_load_dispatch_routes_games_slice(settings: Settings) -> None:
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    result = execute_core_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        slice_key='games',
    )

    from new_nfl.core.games import CoreGameLoadResult
    assert isinstance(result, CoreGameLoadResult)
    assert result.qualified_table == CORE_GAME_TABLE
    assert result.row_count == 4


# ---------------------------------------------------------------------------
# Real HTTP round-trip for the official_context_web adapter (T2.5B).
#
# Spins up a stdlib ThreadingHTTPServer on a free port, serves a tiny CSV
# payload, then drives execute_remote_fetch + execute_stage_load through the
# slice-registry dispatch. No external network, no optional deps.
# ---------------------------------------------------------------------------


_TIER_B_CSV = (
    "game_id,home_score,away_score,stadium\n"
    "2024_01_det_kc,21,24,GEHA Field at Arrowhead Stadium\n"
    "2024_01_sf_nyj,32,19,Levi's Stadium\n"
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


def test_official_context_web_games_real_http_roundtrip(settings: Settings) -> None:
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
        url = f'http://127.0.0.1:{port}/games.csv'

        fetch = execute_remote_fetch(
            settings,
            adapter_id='official_context_web',
            execute=True,
            remote_url_override=url,
            slice_key='games',
        )
        assert fetch.run_status == 'remote_fetched'
        assert fetch.downloaded_bytes == len(_TIER_B_CSV.encode('utf-8'))
        assert Path(fetch.downloaded_file_path).exists()

        stage = execute_stage_load(
            settings,
            adapter_id='official_context_web',
            execute=True,
            source_file_id=None,  # use latest_source_file pin
            slice_key='games',
        )
        cross = get_slice('official_context_web', 'games')
        assert stage.qualified_table == cross.stage_qualified_table
        assert stage.row_count == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_roundtrip_feeds_tier_b_quarantine(settings: Settings) -> None:
    """End-to-end: Tier-A stage + real HTTP Tier-B → quarantine surfaces drift.

    The served CSV reports a different home_score for SF/NYJ than Tier-A,
    so the T2.5B promoter must open exactly one quarantine case after the
    real fetch + stage-load pipeline — no manual stage seeding for Tier-B.
    """
    _seed_tier_a_stage(settings, _TIER_A_ROWS)

    divergent_csv = (
        "game_id,home_score,away_score,stadium\n"
        "2024_01_sf_nyj,35,19,Levi's Stadium\n"
    ).encode('utf-8')
    server = ThreadingHTTPServer(
        ('127.0.0.1', 0),
        _make_handler(divergent_csv),
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{port}/games.csv'
        execute_remote_fetch(
            settings,
            adapter_id='official_context_web',
            execute=True,
            remote_url_override=url,
            slice_key='games',
        )
        execute_stage_load(
            settings,
            adapter_id='official_context_web',
            execute=True,
            source_file_id=None,
            slice_key='games',
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    result = execute_core_game_load(settings, execute=True)
    assert result.conflict_count == 1
    assert len(result.opened_quarantine_case_ids) == 1
    cases = list_quarantine_cases(settings, status_filter='open')
    assert {c.scope_ref for c in cases} == {'2024_01_sf_nyj'}
