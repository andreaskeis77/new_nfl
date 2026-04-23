"""T2.6D — Team-Profil views (ADR-0029).

Covers the read service + two rendered pages (``/teams``,
``/teams/<abbr>``) over the four mart tables
``mart.team_overview_v1``, ``mart.roster_current_v1``,
``mart.team_stats_season_v1`` and ``mart.game_overview_v1``.
Tests seed each mart directly so they do not depend on core-load.
"""
from __future__ import annotations

from datetime import date

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings
from new_nfl.web.renderer import (
    render_team_profile_page,
    render_teams_page,
)
from new_nfl.web.team_view import (
    get_team_profile,
    list_teams,
)


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_team_overview(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.team_overview_v1 (
            team_id VARCHAR,
            team_abbr VARCHAR,
            team_name VARCHAR,
            team_nick VARCHAR,
            team_conference VARCHAR,
            team_division VARCHAR,
            team_color VARCHAR,
            team_color2 VARCHAR,
            first_season INTEGER,
            last_season INTEGER,
            successor_team_id VARCHAR,
            team_id_lower VARCHAR,
            team_abbr_lower VARCHAR,
            team_name_lower VARCHAR,
            is_active BOOLEAN,
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            source_canonicalized_at TIMESTAMP,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO mart.team_overview_v1
              (team_id, team_abbr, team_name, team_nick, team_conference,
               team_division, team_color, first_season, last_season,
               team_id_lower, team_abbr_lower, team_name_lower, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, LOWER(?), LOWER(?), LOWER(?), ?)
            ''',
            (*row[:-1], row[0], row[1], row[2], row[-1]),
        )


def _seed_roster_current(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.roster_current_v1 (
            player_id VARCHAR,
            team_id VARCHAR,
            season INTEGER,
            valid_from_week INTEGER,
            valid_to_week INTEGER,
            last_observed_week INTEGER,
            global_max_week INTEGER,
            position VARCHAR,
            jersey_number INTEGER,
            status VARCHAR,
            display_name VARCHAR,
            team_name VARCHAR,
            team_abbr VARCHAR,
            player_id_lower VARCHAR,
            team_id_lower VARCHAR,
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # row = (player_id, team_id, season, position, jersey, status,
        #        display_name, valid_from_week)
        con.execute(
            '''
            INSERT INTO mart.roster_current_v1
              (player_id, team_id, season, valid_from_week, position,
               jersey_number, status, display_name,
               player_id_lower, team_id_lower)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, LOWER(?), LOWER(?))
            ''',
            (
                row[0], row[1], row[2], row[7], row[3], row[4], row[5], row[6],
                row[0], row[1],
            ),
        )


def _seed_team_stats_season(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.team_stats_season_v1 (
            season INTEGER,
            team_id VARCHAR,
            games_played INTEGER,
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
        con.execute(
            '''
            INSERT INTO mart.team_stats_season_v1
              (season, team_id, games_played, points_for, points_against,
               yards_for, yards_against, turnovers, penalties_for,
               point_diff, yard_diff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            row,
        )


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
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            source_canonicalized_at TIMESTAMP,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO mart.game_overview_v1
              (game_id, season, week, gameday, gametime, home_team, away_team,
               home_score, away_score, stadium, is_completed, winner_team,
               home_team_lower, away_team_lower)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LOWER(?), LOWER(?))
            ''',
            (*row, row[5], row[6]),
        )


def _sample_teams():
    # (team_id, team_abbr, team_name, team_nick, conf, div, color,
    #  first_season, last_season, is_active)
    return [
        ('KC', 'KC', 'Kansas City Chiefs', 'Chiefs',
         'AFC', 'West', '#E31837', 1960, None, True),
        ('BAL', 'BAL', 'Baltimore Ravens', 'Ravens',
         'AFC', 'North', '#241773', 1996, None, True),
        ('PHI', 'PHI', 'Philadelphia Eagles', 'Eagles',
         'NFC', 'East', '#004C54', 1933, None, True),
        ('LA-STL', 'STL', 'St. Louis Rams (historic)', 'Rams',
         'NFC', 'West', '#FFA300', 1995, 2015, False),
    ]


def _sample_roster_kc():
    # rows: (player_id, team_id, season, position, jersey, status, name, from_wk)
    return [
        ('00-0033873', 'KC', 2024, 'QB', 15, 'ACT', 'Patrick Mahomes', 1),
        ('00-0036355', 'KC', 2024, 'TE', 87, 'ACT', 'Travis Kelce', 1),
        ('00-0038500', 'KC', 2024, 'RB', 25, 'ACT', 'Clyde Edwards-Helaire', 3),
    ]


def _sample_team_stats():
    return [
        # (season, team_id, gp, pf, pa, yf, ya, to, pen, point_diff, yard_diff)
        (2024, 'KC', 17, 420, 320, 6100, 5500, 18, 95, 100, 600),
        (2023, 'KC', 17, 380, 310, 5900, 5400, 14, 88, 70, 500),
        (2024, 'BAL', 17, 460, 310, 6600, 5200, 12, 80, 150, 1400),
    ]


def _sample_games_kc():
    # (game_id, season, week, gameday, gametime, home_team, away_team,
    #  home_score, away_score, stadium, is_completed, winner_team)
    return [
        ('2024_01_BAL_KC', 2024, 1, date(2024, 9, 5), '20:20',
         'KC', 'BAL', 27, 20, 'GEHA Field', True, 'KC'),
        ('2024_02_KC_CIN', 2024, 2, date(2024, 9, 15), '20:20',
         'CIN', 'KC', 21, 26, 'Paycor', True, 'KC'),
        ('2024_03_LAC_KC', 2024, 3, date(2024, 9, 22), '16:25',
         'KC', 'LAC', 10, 17, 'GEHA Field', True, 'LAC'),
        ('2024_18_DEN_KC', 2024, 18, date(2025, 1, 5), '16:25',
         'DEN', 'KC', None, None, 'Empower Field', False, None),
        ('2023_01_DET_KC', 2023, 1, date(2023, 9, 7), '20:20',
         'KC', 'DET', 20, 21, 'GEHA Field', True, 'DET'),
    ]


# ---------------------------------------------------------------------------
# Service: list_teams
# ---------------------------------------------------------------------------


def test_list_teams_empty_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    assert list_teams(settings) == ()


def test_list_teams_orders_by_conference_division_name(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_team_stats_season(con, _sample_team_stats())
    finally:
        con.close()
    teams = list_teams(settings)
    # AFC North < AFC West, NFC East < NFC West alphabetically.
    order = [t.team_abbr for t in teams]
    assert order == ['BAL', 'KC', 'PHI', 'STL']


def test_list_teams_enriches_with_latest_season_stats(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_team_stats_season(con, _sample_team_stats())
    finally:
        con.close()
    teams = {t.team_abbr: t for t in list_teams(settings)}
    assert teams['KC'].latest_season == 2024
    assert teams['KC'].latest_points_for == 420
    assert teams['KC'].latest_points_against == 320
    assert teams['KC'].latest_games_played == 17
    # PHI has no stats rows → latest_* stay None.
    assert teams['PHI'].latest_season is None
    assert teams['PHI'].latest_points_for is None


def test_team_card_is_active_flag_reflects_last_season(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    teams = {t.team_abbr: t for t in list_teams(settings)}
    assert teams['KC'].is_active is True
    assert teams['STL'].is_active is False


# ---------------------------------------------------------------------------
# Service: get_team_profile
# ---------------------------------------------------------------------------


def test_get_team_profile_missing_team_returns_none(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    assert get_team_profile(settings, 'NOPE') is None


def test_get_team_profile_case_insensitive_lookup(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    profile = get_team_profile(settings, 'kc')
    assert profile is not None
    assert profile.meta.team_abbr == 'KC'
    assert profile.meta.team_name == 'Kansas City Chiefs'


def test_get_team_profile_returns_roster_ordered_by_position_jersey(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_roster_current(con, _sample_roster_kc())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC')
    assert profile is not None
    positions = [e.position for e in profile.roster]
    assert positions == ['QB', 'RB', 'TE']
    assert profile.roster_size == 3
    assert profile.roster[0].display_label == 'Patrick Mahomes'
    assert profile.roster[0].jersey_label == '#15'


def test_get_team_profile_season_stats_desc(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_team_stats_season(con, _sample_team_stats())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC')
    assert profile is not None
    assert [s.season for s in profile.season_stats] == [2024, 2023]
    assert profile.season_stats[0].point_diff == 100


def test_get_team_profile_defaults_to_most_recent_game_season(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC')
    assert profile is not None
    assert profile.selected_season == 2024
    assert profile.available_seasons == (2024, 2023)
    kept_seasons = {g.season for g in profile.games}
    assert kept_seasons == {2024}


def test_get_team_profile_respects_explicit_season(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC', season=2023)
    assert profile is not None
    assert profile.selected_season == 2023
    assert [g.game_id for g in profile.games] == ['2023_01_DET_KC']


def test_get_team_profile_unknown_season_falls_back_to_latest(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC', season=1999)
    assert profile is not None
    assert profile.selected_season == 2024


def test_get_team_profile_orients_games_from_team_perspective(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC')
    assert profile is not None
    home_opener = next(g for g in profile.games if g.week == 1)
    assert home_opener.is_home is True
    assert home_opener.opponent == 'BAL'
    assert home_opener.score_for == 27
    assert home_opener.score_against == 20
    assert home_opener.outcome == 'win'

    road_game = next(g for g in profile.games if g.week == 2)
    assert road_game.is_home is False
    assert road_game.opponent == 'CIN'
    assert road_game.score_for == 26
    assert road_game.score_against == 21
    assert road_game.outcome == 'win'

    loss = next(g for g in profile.games if g.week == 3)
    assert loss.outcome == 'loss'

    scheduled = next(g for g in profile.games if g.week == 18)
    assert scheduled.outcome == 'scheduled'
    assert scheduled.score_label == '—'


def test_team_profile_record_label_wins_losses(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    profile = get_team_profile(settings, 'KC')
    assert profile is not None
    assert profile.record_label == '2–1'


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_teams_page_lists_all_teams(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_team_stats_season(con, _sample_team_stats())
    finally:
        con.close()
    html = render_teams_page(settings)
    assert 'Kansas City Chiefs' in html
    assert 'Baltimore Ravens' in html
    assert 'data-team-abbr="KC"' in html
    assert 'href="/teams/KC"' in html


def test_render_teams_page_empty_state_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_teams_page(settings)
    assert 'Noch keine Teams geladen' in html


def test_render_team_profile_page_renders_all_sections(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_roster_current(con, _sample_roster_kc())
        _seed_team_stats_season(con, _sample_team_stats())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    html = render_team_profile_page(settings, 'KC')
    assert 'data-testid="team-header"' in html
    assert 'Kansas City Chiefs' in html
    assert 'AFC West' in html
    assert 'Patrick Mahomes' in html
    assert 'data-testid="roster-row"' in html
    assert 'data-testid="season-stats-row"' in html
    assert 'data-testid="team-game-row"' in html
    # Latest season selector shows both available seasons.
    assert 'Verfügbare Saisons' in html
    assert '2024' in html and '2023' in html


def test_render_team_profile_page_not_found(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    html = render_team_profile_page(settings, 'NOPE')
    assert 'Team nicht gefunden' in html
    assert 'NOPE' in html


def test_render_team_profile_breadcrumb_and_active_nav(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    html = render_team_profile_page(settings, 'KC')
    assert 'href="/"' in html
    assert 'href="/teams"' in html
    assert 'nav-link-active' in html


def test_render_team_profile_respects_explicit_season_param(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_team_overview(con, _sample_teams())
        _seed_game_overview(con, _sample_games_kc())
    finally:
        con.close()
    html = render_team_profile_page(settings, 'KC', season=2023)
    assert 'Spiele · Saison 2023' in html
    assert '2023_01_DET_KC' in html
    assert '2024_01_BAL_KC' not in html
