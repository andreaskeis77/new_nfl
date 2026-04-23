"""T2.6G — mart.provenance_v1 + Provenance-Drilldown view (ADR-0029).

End-to-end slice: seeds ``core.*`` domain tables with source_file_id /
source_adapter_id + a couple of ``meta.quarantine_case`` rows, then
rebuilds ``mart.provenance_v1`` and exercises the read service and the
rendered pages (``/provenance``, ``/provenance/<scope_type>``,
``/provenance/<scope_type>/<scope_ref>``). Tests do not depend on
core-load — everything is seeded directly.
"""
from __future__ import annotations

from datetime import datetime

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.mart import build_provenance_v1
from new_nfl.settings import load_settings
from new_nfl.web.provenance_view import (
    ProvenanceRecord,
    get_provenance,
    list_provenance,
)
from new_nfl.web.renderer import (
    render_provenance_detail_page,
    render_provenance_page,
)


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_core_team(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS core')
    con.execute(
        '''
        CREATE OR REPLACE TABLE core.team (
            team_id VARCHAR,
            team_name VARCHAR,
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            source_canonicalized_at TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO core.team
              (team_id, team_name, source_file_id, source_adapter_id,
               source_canonicalized_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            row,
        )


def _seed_core_game(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS core')
    con.execute(
        '''
        CREATE OR REPLACE TABLE core.game (
            game_id VARCHAR,
            season INTEGER,
            week INTEGER,
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            source_canonicalized_at TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO core.game
              (game_id, season, week, source_file_id, source_adapter_id,
               source_canonicalized_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            row,
        )


def _seed_core_team_stats_weekly(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS core')
    con.execute(
        '''
        CREATE OR REPLACE TABLE core.team_stats_weekly (
            team_id VARCHAR,
            season INTEGER,
            week INTEGER,
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            source_canonicalized_at TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO core.team_stats_weekly
              (team_id, season, week, source_file_id, source_adapter_id,
               source_canonicalized_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            row,
        )


def _seed_quarantine_cases(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS meta')
    con.execute(
        '''
        CREATE TABLE IF NOT EXISTS meta.quarantine_case (
            quarantine_case_id VARCHAR,
            scope_type VARCHAR,
            scope_ref VARCHAR,
            reason_code VARCHAR,
            severity VARCHAR,
            status VARCHAR,
            first_seen_at TIMESTAMP,
            last_seen_at TIMESTAMP,
            resolved_at TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO meta.quarantine_case
              (quarantine_case_id, scope_type, scope_ref, reason_code,
               severity, status, first_seen_at, last_seen_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            row,
        )


def _sample_teams():
    # (team_id, team_name, source_file_id, source_adapter_id,
    #  source_canonicalized_at)
    t1 = datetime(2026, 4, 20, 10, 0, 0)
    t2 = datetime(2026, 4, 21, 10, 0, 0)
    return [
        ('KC', 'Kansas City Chiefs', 'sf-team-001', 'nflverse_bulk', t1),
        ('BAL', 'Baltimore Ravens', 'sf-team-001', 'nflverse_bulk', t1),
        ('NE', 'New England Patriots', 'sf-team-002', 'nflverse_bulk', t2),
    ]


def _sample_games():
    # (game_id, season, week, source_file_id, source_adapter_id,
    #  source_canonicalized_at)
    t = datetime(2026, 4, 22, 12, 0, 0)
    return [
        ('2024_01_BAL_KC', 2024, 1, 'sf-game-001', 'nflverse_bulk', t),
        ('2024_02_KC_CIN', 2024, 2, 'sf-game-001', 'nflverse_bulk', t),
    ]


def _sample_team_stats_weekly():
    t = datetime(2026, 4, 22, 13, 0, 0)
    return [
        # KC week 1
        ('KC', 2024, 1, 'sf-tsw-001', 'nflverse_bulk', t),
        # BAL week 1
        ('BAL', 2024, 1, 'sf-tsw-001', 'nflverse_bulk', t),
    ]


def _sample_quarantine_cases():
    # (qc_id, scope_type, scope_ref, reason_code, severity, status,
    #  first_seen_at, last_seen_at, resolved_at)
    t1 = datetime(2026, 4, 20, 9, 0, 0)
    t2 = datetime(2026, 4, 22, 14, 0, 0)
    return [
        # Open case for KC week 1
        ('qc-001', 'team_stats_weekly', 'KC:2024:W01',
         'points_mismatch', 'warn', 'open', t1, t2, None),
        # Closed case for same scope
        ('qc-002', 'team_stats_weekly', 'KC:2024:W01',
         'yards_mismatch', 'info', 'resolved', t1, t1, t1),
        # Open case for a scope with NO source rows (drift detection only)
        ('qc-003', 'player', '00-0012345',
         'duplicate_candidate', 'warn', 'open', t2, t2, None),
    ]


# ---------------------------------------------------------------------------
# Mart builder tests
# ---------------------------------------------------------------------------


def test_build_provenance_v1_empty_environment(tmp_path, monkeypatch):
    """Cold-start: no core.*, no meta.quarantine_case → empty mart."""
    settings = _bootstrap(tmp_path, monkeypatch)
    result = build_provenance_v1(settings)
    assert result.qualified_table == 'mart.provenance_v1'
    assert result.row_count == 0


def test_build_provenance_v1_with_core_only(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
        _seed_core_game(con, _sample_games())
    finally:
        con.close()
    build_provenance_v1(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            '''
            SELECT scope_type, scope_ref, source_row_count,
                   open_quarantine_count, provenance_status
            FROM mart.provenance_v1
            ORDER BY scope_type, scope_ref
            '''
        ).fetchall()
    finally:
        con.close()
    scope_keys = {(r[0], r[1]) for r in rows}
    # 3 teams + 2 games = 5 scopes
    assert len(rows) == 5
    assert ('team', 'KC') in scope_keys
    assert ('team', 'BAL') in scope_keys
    assert ('game', '2024_01_BAL_KC') in scope_keys
    # All 'ok' because no quarantine
    assert all(r[4] == 'ok' for r in rows)


def test_build_provenance_v1_joins_source_and_quarantine(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team_stats_weekly(con, _sample_team_stats_weekly())
        _seed_quarantine_cases(con, _sample_quarantine_cases())
    finally:
        con.close()
    build_provenance_v1(settings)
    record = get_provenance(settings, 'team_stats_weekly', 'KC:2024:W01')
    assert record is not None
    assert record.source_row_count == 1  # one core row
    assert record.quarantine_case_count == 2  # one open, one resolved
    assert record.open_quarantine_count == 1
    assert record.provenance_status == 'warn'
    assert record.last_reason_code == 'points_mismatch'
    assert 'sf-tsw-001' in record.source_file_ids
    assert 'nflverse_bulk' in record.source_adapter_ids


def test_build_provenance_v1_quarantine_without_source(tmp_path, monkeypatch):
    """Quarantine case whose scope has no core row still produces a scope row."""
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_quarantine_cases(con, _sample_quarantine_cases())
    finally:
        con.close()
    build_provenance_v1(settings)
    record = get_provenance(settings, 'player', '00-0012345')
    assert record is not None
    assert record.source_row_count == 0
    assert record.source_file_ids == ()
    assert record.open_quarantine_count == 1
    assert record.provenance_status == 'warn'


# ---------------------------------------------------------------------------
# Read service tests
# ---------------------------------------------------------------------------


def test_list_provenance_empty_when_mart_missing(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    page = list_provenance(settings)
    assert page.rows == ()
    assert page.total == 0
    assert page.has_prev is False
    assert page.has_next is False


def test_list_provenance_orders_warns_first(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
        _seed_core_team_stats_weekly(con, _sample_team_stats_weekly())
        _seed_quarantine_cases(con, _sample_quarantine_cases())
    finally:
        con.close()
    build_provenance_v1(settings)
    page = list_provenance(settings)
    assert page.total == 3 + 2 + 1  # 3 teams + 2 tsw + 1 quarantine-only player
    # First row must be a warn scope (open_quarantine_count > 0)
    assert page.rows[0].open_quarantine_count > 0


def test_list_provenance_filters_by_scope_type(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
        _seed_core_game(con, _sample_games())
    finally:
        con.close()
    build_provenance_v1(settings)
    page = list_provenance(settings, scope_type='game')
    assert page.total == 2
    assert all(r.scope_type == 'game' for r in page.rows)
    assert page.scope_type_filter == 'game'
    # Case-insensitive filter.
    upper = list_provenance(settings, scope_type='GAME')
    assert upper.total == 2


def test_list_provenance_pagination(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
        _seed_core_game(con, _sample_games())
    finally:
        con.close()
    build_provenance_v1(settings)
    page1 = list_provenance(settings, offset=0, limit=2)
    assert page1.total == 5
    assert len(page1.rows) == 2
    assert page1.has_prev is False
    assert page1.has_next is True
    assert page1.page_range_label == '1–2 von 5'
    page2 = list_provenance(settings, offset=2, limit=2)
    assert len(page2.rows) == 2
    assert page2.has_prev is True


def test_get_provenance_case_insensitive(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
    finally:
        con.close()
    build_provenance_v1(settings)
    lower = get_provenance(settings, 'team', 'kc')
    upper = get_provenance(settings, 'TEAM', 'KC')
    assert lower is not None and upper is not None
    assert isinstance(lower, ProvenanceRecord)
    assert lower.scope_ref == 'KC'
    assert upper.scope_ref == 'KC'


def test_get_provenance_returns_none_for_unknown(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    assert get_provenance(settings, 'team', 'MISSING') is None


def test_quarantine_label_format(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team_stats_weekly(con, _sample_team_stats_weekly())
        _seed_quarantine_cases(con, _sample_quarantine_cases())
    finally:
        con.close()
    build_provenance_v1(settings)
    record = get_provenance(settings, 'team_stats_weekly', 'KC:2024:W01')
    assert record is not None
    # 2 total, 1 open → "1 offen / 2 total"
    assert record.quarantine_label == '1 offen / 2 total'


# ---------------------------------------------------------------------------
# Render tests
# ---------------------------------------------------------------------------


def test_render_provenance_page_empty(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_provenance_page(settings)
    assert 'Provenienz-Index' in html
    assert 'Noch keine Provenienz-Zeilen' in html


def test_render_provenance_page_with_rows(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
        _seed_quarantine_cases(con, _sample_quarantine_cases())
    finally:
        con.close()
    build_provenance_v1(settings)
    html = render_provenance_page(settings)
    assert 'data-testid="provenance-row"' in html
    assert 'data-scope-ref="KC"' in html
    assert '/provenance/team/KC' in html


def test_render_provenance_detail_page_404(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_provenance_detail_page(settings, 'team', 'MISSING')
    assert 'Scope nicht gefunden' in html
    assert 'MISSING' in html


def test_render_provenance_detail_page_happy(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team_stats_weekly(con, _sample_team_stats_weekly())
        _seed_quarantine_cases(con, _sample_quarantine_cases())
    finally:
        con.close()
    build_provenance_v1(settings)
    html = render_provenance_detail_page(
        settings, 'team_stats_weekly', 'KC:2024:W01',
    )
    assert 'data-testid="provenance-header"' in html
    assert 'data-scope-ref="KC:2024:W01"' in html
    assert 'sf-tsw-001' in html
    assert 'points_mismatch' in html
    # Breadcrumb chain includes intermediate scope_type link
    assert 'Provenance' in html
    assert 'team_stats_weekly' in html


def test_render_provenance_page_scope_type_filter(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_core_team(con, _sample_teams())
        _seed_core_game(con, _sample_games())
    finally:
        con.close()
    build_provenance_v1(settings)
    html = render_provenance_page(settings, scope_type='game')
    assert 'Provenienz · game' in html
    assert '2024_01_BAL_KC' in html
    # Team rows should NOT appear.
    assert 'data-scope-ref="KC"' not in html
