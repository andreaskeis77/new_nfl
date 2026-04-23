"""T2.6F — Game-Detail Pre/Post views (ADR-0029).

Exercises the read service plus the rendered ``/games/<game_id>`` page
against four mart tables: ``mart.game_overview_v1``,
``mart.team_stats_weekly_v1``, ``mart.player_stats_weekly_v1`` and the
optional ``mart.team_overview_v1`` JOIN for team names. Tests seed each
mart directly — no core-load dependency.

Cold-start-per-mart discipline: every mart dependency must be provable
absent on its own. Three tests exercise a different missing mart so
graceful-degradation regressions are caught at the correct seam.
"""
from __future__ import annotations

from datetime import date

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings
from new_nfl.web.game_view import (
    GameDetail,
    get_game_detail,
)
from new_nfl.web.renderer import render_game_detail_page


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_game_overview(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.game_overview_v1 (
            game_id VARCHAR,
            season INTEGER,
            game_type VARCHAR,
            week INTEGER,
            gameday DATE,
            weekday VARCHAR,
            gametime VARCHAR,
            home_team VARCHAR,
            away_team VARCHAR,
            home_score INTEGER,
            away_score INTEGER,
            result DOUBLE,
            overtime INTEGER,
            stadium VARCHAR,
            roof VARCHAR,
            surface VARCHAR,
            game_id_lower VARCHAR,
            home_team_lower VARCHAR,
            away_team_lower VARCHAR,
            is_completed BOOLEAN,
            winner_team VARCHAR,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # row = (game_id, season, game_type, week, gameday, weekday, gametime,
        #        home, away, home_score, away_score, overtime, stadium, roof,
        #        surface, is_completed, winner_team)
        con.execute(
            '''
            INSERT INTO mart.game_overview_v1
              (game_id, season, game_type, week, gameday, weekday, gametime,
               home_team, away_team, home_score, away_score, overtime,
               stadium, roof, surface, is_completed, winner_team,
               game_id_lower, home_team_lower, away_team_lower)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    LOWER(?), LOWER(?), LOWER(?))
            ''',
            (*row, row[0], row[7], row[8]),
        )


def _seed_team_overview(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.team_overview_v1 (
            team_id VARCHAR,
            team_abbr VARCHAR,
            team_name VARCHAR,
            team_id_lower VARCHAR,
            team_abbr_lower VARCHAR,
            team_name_lower VARCHAR,
            is_active BOOLEAN,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # (team_id, team_abbr, team_name, is_active)
        con.execute(
            '''
            INSERT INTO mart.team_overview_v1
              (team_id, team_abbr, team_name, team_id_lower, team_abbr_lower,
               team_name_lower, is_active)
            VALUES (?, ?, ?, LOWER(?), LOWER(?), LOWER(?), ?)
            ''',
            (row[0], row[1], row[2], row[0], row[1], row[2], row[3]),
        )


def _seed_team_week(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.team_stats_weekly_v1 (
            season INTEGER,
            week INTEGER,
            team_id VARCHAR,
            opponent_team_id VARCHAR,
            points_for INTEGER,
            points_against INTEGER,
            yards_for INTEGER,
            yards_against INTEGER,
            turnovers INTEGER,
            penalties_for INTEGER,
            point_diff INTEGER,
            yard_diff INTEGER,
            team_name VARCHAR,
            team_abbr VARCHAR,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # (season, week, team_id, opponent, pf, pa, yf, ya, to, pen)
        pf, pa, yf, ya = row[4], row[5], row[6], row[7]
        point_diff = (pf - pa) if (pf is not None and pa is not None) else None
        yard_diff = (yf - ya) if (yf is not None and ya is not None) else None
        con.execute(
            '''
            INSERT INTO mart.team_stats_weekly_v1
              (season, week, team_id, opponent_team_id, points_for,
               points_against, yards_for, yards_against, turnovers,
               penalties_for, point_diff, yard_diff, team_abbr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (*row, point_diff, yard_diff, row[2]),
        )


def _seed_player_week(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.player_stats_weekly_v1 (
            season INTEGER,
            week INTEGER,
            player_id VARCHAR,
            team_id VARCHAR,
            position VARCHAR,
            passing_yards INTEGER,
            passing_tds INTEGER,
            interceptions INTEGER,
            rushing_yards INTEGER,
            rushing_tds INTEGER,
            receptions INTEGER,
            receiving_yards INTEGER,
            receiving_tds INTEGER,
            touchdowns INTEGER,
            fumbles_lost INTEGER,
            total_yards INTEGER,
            total_touchdowns INTEGER,
            display_name VARCHAR,
            team_abbr VARCHAR,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # (season, week, player_id, team_id, position, display_name,
        #  passing_yards, passing_tds, rushing_yards, rushing_tds,
        #  receptions, receiving_yards, receiving_tds)
        py, pt = row[6], row[7]
        ry, rt = row[8], row[9]
        recy, rect = row[11], row[12]
        total_yards = sum(v for v in (py, ry, recy) if v is not None) or None
        total_tds = sum(v for v in (pt, rt, rect) if v is not None) or None
        con.execute(
            '''
            INSERT INTO mart.player_stats_weekly_v1
              (season, week, player_id, team_id, position, display_name,
               passing_yards, passing_tds, rushing_yards, rushing_tds,
               receptions, receiving_yards, receiving_tds,
               total_yards, total_touchdowns, team_abbr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (*row, total_yards, total_tds, row[3]),
        )


def _sample_games():
    # (game_id, season, game_type, week, gameday, weekday, gametime,
    #  home, away, home_score, away_score, overtime, stadium, roof, surface,
    #  is_completed, winner_team)
    return [
        ('2024_02_BAL_KC', 2024, 'REG', 2, date(2024, 9, 15), 'Sunday', '20:20',
         'KC', 'BAL', 27, 20, 0,
         'GEHA Field', 'outdoors', 'grass', True, 'KC'),
        ('2024_01_KC_CIN', 2024, 'REG', 1, date(2024, 9, 8), 'Sunday', '13:00',
         'KC', 'CIN', 17, 10, 0,
         'GEHA Field', 'outdoors', 'grass', True, 'KC'),
        ('2024_03_KC_LAC', 2024, 'REG', 3, date(2024, 9, 22), 'Sunday', '20:20',
         'LAC', 'KC', None, None, None,
         'SoFi Stadium', 'dome', 'turf', False, None),
        ('2024_04_KC_NE_OT', 2024, 'REG', 4, date(2024, 9, 29), 'Sunday', '13:00',
         'NE', 'KC', 20, 20, 1,
         'Gillette Stadium', 'outdoors', 'grass', True, 'TIE'),
    ]


def _sample_teams():
    return [
        ('KC', 'KC', 'Kansas City Chiefs', True),
        ('BAL', 'BAL', 'Baltimore Ravens', True),
        ('CIN', 'CIN', 'Cincinnati Bengals', True),
        ('LAC', 'LAC', 'Los Angeles Chargers', True),
        ('NE', 'NE', 'New England Patriots', True),
    ]


def _sample_team_week():
    # Pre-game: week 1 KC win, week 1 BAL loss; week 2 is the game of interest.
    # For '2024_02_BAL_KC' (week 2) pre-game window (week < 2):
    #   KC: 17-10 → W, PF=17, PA=10
    #   BAL: lost to some week-1 opponent 14-30 → L, PF=14, PA=30
    # For week 2 (post-game): KC 27-20, BAL 20-27.
    return [
        (2024, 1, 'KC', 'CIN', 17, 10, 320, 250, 1, 50),
        (2024, 1, 'BAL', 'LV', 14, 30, 280, 350, 2, 60),
        (2024, 2, 'KC', 'BAL', 27, 20, 380, 310, 1, 40),
        (2024, 2, 'BAL', 'KC', 20, 27, 310, 380, 2, 55),
    ]


def _sample_player_week():
    # (season, week, player_id, team_id, position, display_name,
    #  passing_yards, passing_tds, rushing_yards, rushing_tds,
    #  receptions, receiving_yards, receiving_tds)
    return [
        # KC week 2 — Mahomes big, Kelce medium, Pacheco smaller
        (2024, 2, '00-0033873', 'KC', 'QB', 'P.Mahomes',
         312, 2, 20, 0, 0, 0, 0),
        (2024, 2, '00-0036355', 'KC', 'TE', 'T.Kelce',
         0, 0, 0, 0, 7, 85, 1),
        (2024, 2, '00-PACH', 'KC', 'RB', 'I.Pacheco',
         0, 0, 95, 1, 2, 12, 0),
        # BAL week 2 — Jackson, Andrews, Flowers
        (2024, 2, '00-JACK', 'BAL', 'QB', 'L.Jackson',
         230, 1, 75, 1, 0, 0, 0),
        (2024, 2, '00-ANDR', 'BAL', 'TE', 'M.Andrews',
         0, 0, 0, 0, 5, 60, 0),
        (2024, 2, '00-FLOW', 'BAL', 'WR', 'Z.Flowers',
         0, 0, 0, 0, 6, 72, 1),
    ]


def test_get_game_detail_empty_when_mart_missing(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    detail = get_game_detail(settings, '2024_02_BAL_KC')
    assert detail is None


def test_get_game_detail_returns_none_for_unknown_game(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
    finally:
        con.close()
    assert get_game_detail(settings, '9999_99_FOO_BAR') is None


def test_get_game_detail_post_game_full_bundle(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_team_week(con, _sample_team_week())
        _seed_player_week(con, _sample_player_week())
    finally:
        con.close()
    detail = get_game_detail(settings, '2024_02_BAL_KC')
    assert detail is not None
    assert isinstance(detail, GameDetail)
    # Meta
    assert detail.meta.home_team == 'KC'
    assert detail.meta.away_team == 'BAL'
    assert detail.meta.home_team_name == 'Kansas City Chiefs'
    assert detail.meta.away_team_name == 'Baltimore Ravens'
    assert detail.meta.is_completed is True
    assert detail.is_pre_game is False
    assert detail.meta.score_label == '27 – 20'
    assert detail.meta.status_label == 'Final'
    assert detail.meta.winner_label == 'Kansas City Chiefs'
    assert detail.meta.venue_label == 'GEHA Field · outdoors · grass'
    assert detail.meta.matchup_label == 'BAL @ KC'
    # Form (pre-game, from week 1 only)
    assert detail.home_form is not None
    assert detail.home_form.team_abbr == 'KC'
    assert detail.home_form.games_played == 1
    assert detail.home_form.wins == 1
    assert detail.home_form.losses == 0
    assert detail.home_form.record_label == '1–0'
    assert detail.home_form.points_for == 17
    assert detail.home_form.points_against == 10
    assert detail.home_form.avg_points_for == 17.0
    assert detail.away_form is not None
    assert detail.away_form.wins == 0
    assert detail.away_form.losses == 1
    assert detail.away_form.record_label == '0–1'
    # Team week (post-game)
    assert detail.home_week is not None
    assert detail.home_week.points_for == 27
    assert detail.home_week.yards_for == 380
    assert detail.home_week.turnovers == 1
    assert detail.home_week.point_diff == 7
    assert detail.away_week is not None
    assert detail.away_week.points_for == 20
    # Boxscore
    assert len(detail.home_boxscore) == 3
    assert detail.home_boxscore[0].display_name == 'P.Mahomes'
    assert detail.home_boxscore[0].total_yards == 332
    assert detail.home_boxscore[1].display_name == 'I.Pacheco'
    assert detail.home_boxscore[2].display_name == 'T.Kelce'
    assert len(detail.away_boxscore) == 3
    assert detail.away_boxscore[0].display_name == 'L.Jackson'


def test_get_game_detail_pre_game_has_form_but_no_week_or_boxscore(
    tmp_path, monkeypatch
):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_team_week(con, _sample_team_week())
        _seed_player_week(con, _sample_player_week())
    finally:
        con.close()
    # Week 3 LAC vs KC is pre-game.
    detail = get_game_detail(settings, '2024_03_KC_LAC')
    assert detail is not None
    assert detail.is_pre_game is True
    assert detail.meta.status_label == 'geplant'
    assert detail.meta.score_label == '—'
    assert detail.meta.winner_label == '—'
    # Form is still populated (aggregated from earlier weeks).
    assert detail.home_form is not None  # LAC: no earlier weeks → 0 games
    assert detail.home_form.games_played == 0
    assert detail.away_form is not None  # KC: weeks 1 + 2
    assert detail.away_form.games_played == 2
    assert detail.away_form.wins == 2
    # Post-game slices must be empty for a pre-game.
    assert detail.home_week is None
    assert detail.away_week is None
    assert detail.home_boxscore == ()
    assert detail.away_boxscore == ()


def test_get_game_detail_tie_resolves_winner_label(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    detail = get_game_detail(settings, '2024_04_KC_NE_OT')
    assert detail is not None
    assert detail.meta.status_label == 'Final (OT)'
    assert detail.meta.winner_label == 'Unentschieden'


def test_get_game_detail_case_insensitive_lookup(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
    finally:
        con.close()
    lower = get_game_detail(settings, '2024_02_bal_kc')
    upper = get_game_detail(settings, '2024_02_BAL_KC')
    assert lower is not None and upper is not None
    assert lower.meta.game_id == upper.meta.game_id == '2024_02_BAL_KC'


def test_get_game_detail_without_team_overview(tmp_path, monkeypatch):
    # Missing mart.team_overview_v1 → meta loads, team names are None.
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_week(con, _sample_team_week())
    finally:
        con.close()
    detail = get_game_detail(settings, '2024_02_BAL_KC')
    assert detail is not None
    assert detail.meta.home_team_name is None
    assert detail.meta.away_team_name is None
    assert detail.meta.home_label == 'KC'  # falls back to abbr
    assert detail.meta.winner_label == 'KC'  # falls back to abbr
    # Form still works.
    assert detail.home_form is not None
    assert detail.home_form.wins == 1


def test_get_game_detail_without_team_week_mart(tmp_path, monkeypatch):
    # Missing mart.team_stats_weekly_v1 → form + week return None.
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_player_week(con, _sample_player_week())
    finally:
        con.close()
    detail = get_game_detail(settings, '2024_02_BAL_KC')
    assert detail is not None
    assert detail.home_form is None
    assert detail.away_form is None
    assert detail.home_week is None
    assert detail.away_week is None
    # Boxscore must still work.
    assert len(detail.home_boxscore) == 3


def test_get_game_detail_without_player_week_mart(tmp_path, monkeypatch):
    # Missing mart.player_stats_weekly_v1 → boxscore tuples empty.
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_team_week(con, _sample_team_week())
    finally:
        con.close()
    detail = get_game_detail(settings, '2024_02_BAL_KC')
    assert detail is not None
    assert detail.home_boxscore == ()
    assert detail.away_boxscore == ()
    assert detail.home_week is not None
    assert detail.home_form is not None


def test_boxscore_ordering_respects_total_yards_desc(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_team_week(con, _sample_team_week())
        _seed_player_week(con, _sample_player_week())
    finally:
        con.close()
    detail = get_game_detail(settings, '2024_02_BAL_KC')
    assert detail is not None
    yds = [p.total_yards for p in detail.home_boxscore]
    assert yds == sorted(yds, reverse=True)


def test_render_game_detail_page_pre_game(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_team_week(con, _sample_team_week())
    finally:
        con.close()
    html = render_game_detail_page(settings, '2024_03_KC_LAC')
    assert 'data-testid="game-header"' in html
    assert 'data-game-id="2024_03_KC_LAC"' in html
    assert 'pre-game' in html
    assert 'Form vor dem Spiel' in html
    assert 'geplant' in html
    assert 'data-nav-key="seasons"' in html or 'active_nav' not in html
    # Breadcrumb chain
    assert 'Season 2024' in html
    assert 'Woche 3' in html


def test_render_game_detail_page_post_game(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_game_overview(con, _sample_games())
        _seed_team_overview(con, _sample_teams())
        _seed_team_week(con, _sample_team_week())
        _seed_player_week(con, _sample_player_week())
    finally:
        con.close()
    html = render_game_detail_page(settings, '2024_02_BAL_KC')
    assert 'data-testid="post-game-teams"' in html
    assert 'data-testid="post-game-boxscore"' in html
    assert 'P.Mahomes' in html
    assert 'L.Jackson' in html
    assert '27 &#8211; 20' in html or '27 – 20' in html
    assert 'Kansas City Chiefs' in html


def test_render_game_detail_page_404(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_game_detail_page(settings, 'MISSING')
    assert 'Spiel nicht gefunden' in html
    assert 'MISSING' in html
