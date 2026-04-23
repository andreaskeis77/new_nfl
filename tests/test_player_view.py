"""T2.6E — Player-Profil views (ADR-0029).

Covers the read service + two rendered pages (``/players``,
``/players/<player_id>``) over the four mart tables
``mart.player_overview_v1``, ``mart.player_stats_career_v1``,
``mart.player_stats_season_v1`` and ``mart.roster_history_v1``. Tests
seed each mart directly so they do not depend on core-load.
"""
from __future__ import annotations

from datetime import date

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings
from new_nfl.web.player_view import (
    get_player_profile,
    list_players,
)
from new_nfl.web.renderer import (
    render_player_profile_page,
    render_players_page,
)


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_player_overview(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.player_overview_v1 (
            player_id VARCHAR,
            display_name VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            full_name VARCHAR,
            birth_date DATE,
            position VARCHAR,
            height INTEGER,
            weight INTEGER,
            college_name VARCHAR,
            rookie_season INTEGER,
            last_season INTEGER,
            current_team_id VARCHAR,
            jersey_number INTEGER,
            draft_club VARCHAR,
            draft_year INTEGER,
            draft_round INTEGER,
            draft_pick INTEGER,
            status VARCHAR,
            player_id_lower VARCHAR,
            display_name_lower VARCHAR,
            position_lower VARCHAR,
            current_team_id_lower VARCHAR,
            is_active BOOLEAN,
            position_is_known BOOLEAN,
            source_file_id VARCHAR,
            source_adapter_id VARCHAR,
            source_canonicalized_at TIMESTAMP,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # row = (player_id, display_name, first_name, last_name, full_name,
        #        birth_date, position, height, weight, college,
        #        rookie_season, last_season, current_team_id, jersey,
        #        draft_club, draft_year, draft_round, draft_pick, status,
        #        is_active)
        con.execute(
            '''
            INSERT INTO mart.player_overview_v1
              (player_id, display_name, first_name, last_name, full_name,
               birth_date, position, height, weight, college_name,
               rookie_season, last_season, current_team_id, jersey_number,
               draft_club, draft_year, draft_round, draft_pick, status,
               player_id_lower, display_name_lower, position_lower,
               current_team_id_lower, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    LOWER(?), LOWER(COALESCE(?, '')),
                    LOWER(COALESCE(CAST(? AS VARCHAR), '')),
                    LOWER(COALESCE(CAST(? AS VARCHAR), '')),
                    ?)
            ''',
            (
                *row[:-1],
                row[0], row[1], row[6], row[12],
                row[-1],
            ),
        )


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
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # (team_id, team_abbr, team_name, conf, div, first_season, last_season,
        #  is_active)
        con.execute(
            '''
            INSERT INTO mart.team_overview_v1
              (team_id, team_abbr, team_name, team_conference, team_division,
               first_season, last_season, team_id_lower, team_abbr_lower,
               team_name_lower, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, LOWER(?), LOWER(?), LOWER(?), ?)
            ''',
            (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                row[0], row[1], row[2], row[7],
            ),
        )


def _seed_career(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.player_stats_career_v1 (
            player_id VARCHAR,
            first_season INTEGER,
            last_season INTEGER,
            seasons_played INTEGER,
            games_played INTEGER,
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
            current_position VARCHAR,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO mart.player_stats_career_v1
              (player_id, first_season, last_season, seasons_played,
               games_played, passing_yards, passing_tds, interceptions,
               rushing_yards, rushing_tds, receptions, receiving_yards,
               receiving_tds, total_yards, total_touchdowns, fumbles_lost,
               current_position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            row,
        )


def _seed_season_stats(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.player_stats_season_v1 (
            season INTEGER,
            player_id VARCHAR,
            primary_position VARCHAR,
            games_played INTEGER,
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
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        con.execute(
            '''
            INSERT INTO mart.player_stats_season_v1
              (season, player_id, primary_position, games_played,
               passing_yards, passing_tds, interceptions,
               rushing_yards, rushing_tds, receptions, receiving_yards,
               receiving_tds, total_yards, total_touchdowns, fumbles_lost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            row,
        )


def _seed_roster_history(con: duckdb.DuckDBPyConnection, rows) -> None:
    con.execute('CREATE SCHEMA IF NOT EXISTS mart')
    con.execute(
        '''
        CREATE OR REPLACE TABLE mart.roster_history_v1 (
            player_id VARCHAR,
            team_id VARCHAR,
            season INTEGER,
            valid_from_week INTEGER,
            valid_to_week INTEGER,
            last_observed_week INTEGER,
            global_max_week INTEGER,
            is_open BOOLEAN,
            position VARCHAR,
            jersey_number INTEGER,
            status VARCHAR,
            display_name VARCHAR,
            team_name VARCHAR,
            team_abbr VARCHAR,
            player_id_lower VARCHAR,
            team_id_lower VARCHAR,
            built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    for row in rows:
        # (player_id, team_id, season, valid_from, valid_to,
        #  position, jersey, status, team_abbr, team_name)
        is_open = row[4] is None
        con.execute(
            '''
            INSERT INTO mart.roster_history_v1
              (player_id, team_id, season, valid_from_week, valid_to_week,
               is_open, position, jersey_number, status, team_abbr, team_name,
               player_id_lower, team_id_lower)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LOWER(?), LOWER(?))
            ''',
            (
                row[0], row[1], row[2], row[3], row[4], is_open,
                row[5], row[6], row[7], row[8], row[9],
                row[0], row[1],
            ),
        )


def _sample_players():
    # (player_id, display_name, first, last, full, birth, pos, height, weight,
    #  college, rookie, last_season, current_team_id, jersey, draft_club,
    #  draft_year, draft_round, draft_pick, status, is_active)
    return [
        ('00-0033873', 'P.Mahomes', 'Patrick', 'Mahomes', 'Patrick Mahomes',
         date(1995, 9, 17), 'QB', 74, 225, 'Texas Tech',
         2017, None, 'KC', 15, 'KC', 2017, 1, 10, 'ACT', True),
        ('00-0036355', 'T.Kelce', 'Travis', 'Kelce', 'Travis Kelce',
         date(1989, 10, 5), 'TE', 77, 250, 'Cincinnati',
         2013, None, 'KC', 87, 'KC', 2013, 3, 63, 'ACT', True),
        ('00-0020531', 'T.Brady', 'Tom', 'Brady', 'Tom Brady',
         date(1977, 8, 3), 'QB', 76, 225, 'Michigan',
         2000, 2022, None, 12, 'NE', 2000, 6, 199, 'RET', False),
        ('00-0030524', 'O.Beckham', 'Odell', 'Beckham Jr.', 'Odell Beckham Jr.',
         date(1992, 11, 5), 'WR', 71, 198, 'LSU',
         2014, 2023, None, 13, 'NYG', 2014, 1, 12, 'RET', False),
    ]


def _sample_teams():
    return [
        ('KC', 'KC', 'Kansas City Chiefs', 'AFC', 'West', 1960, None, True),
        ('NE', 'NE', 'New England Patriots', 'AFC', 'East', 1960, None, True),
    ]


def _sample_career_mahomes():
    # (player_id, first, last, seasons, games, passY, passTD, int, rushY,
    #  rushTD, rec, recY, recTD, total_yards, total_tds, fumbles,
    #  current_position)
    return [
        ('00-0033873', 2017, 2024, 8, 120, 32000, 250, 75, 1400, 15,
         0, 0, 0, 33400, 265, 22, 'QB'),
    ]


def _sample_season_stats_mahomes():
    # (season, player_id, primary_position, games, passY, passTD, int,
    #  rushY, rushTD, rec, recY, recTD, total_yards, total_tds, fumbles)
    return [
        (2024, '00-0033873', 'QB', 17, 4200, 30, 9, 250, 3, 0, 0, 0, 4450, 33, 3),
        (2023, '00-0033873', 'QB', 17, 4200, 27, 14, 389, 0, 0, 0, 0, 4589, 27, 5),
        (2022, '00-0033873', 'QB', 17, 5250, 41, 12, 358, 4, 0, 0, 0, 5608, 45, 4),
    ]


def _sample_roster_history_mahomes():
    # (player_id, team_id, season, from, to, position, jersey, status,
    #  team_abbr, team_name)
    return [
        ('00-0033873', 'KC', 2017, 1, 17, 'QB', 15, 'ACT', 'KC', 'Kansas City Chiefs'),
        ('00-0033873', 'KC', 2024, 1, None, 'QB', 15, 'ACT', 'KC', 'Kansas City Chiefs'),
        ('00-0033873', 'KC', 2023, 1, 17, 'QB', 15, 'ACT', 'KC', 'Kansas City Chiefs'),
    ]


# ---------------------------------------------------------------------------
# Service: list_players
# ---------------------------------------------------------------------------


def test_list_players_empty_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    page = list_players(settings)
    assert page.players == ()
    assert page.total == 0
    assert page.has_prev is False
    assert page.has_next is False


def test_list_players_orders_active_then_recent(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    page = list_players(settings)
    # Active first (is_active DESC), then last_season DESC NULLS LAST,
    # then display_name. Active players have last_season=None and sort last
    # among active due to NULLS LAST, so alphabetical order wins.
    ids = [p.player_id for p in page.players]
    assert ids[0:2] == ['00-0033873', '00-0036355']  # Mahomes, Kelce (active, alpha)
    assert ids[2:] == ['00-0030524', '00-0020531']  # Beckham 2023, Brady 2022
    assert page.total == 4


def test_list_players_enriches_team_abbr_via_join(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    page = list_players(settings)
    by_id = {p.player_id: p for p in page.players}
    assert by_id['00-0033873'].current_team_abbr == 'KC'
    assert by_id['00-0020531'].current_team_abbr is None


def test_list_players_works_without_team_mart(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    page = list_players(settings)
    assert page.total == 4
    assert all(p.current_team_abbr is None for p in page.players)


def test_list_players_pagination_offset_and_limit(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    first = list_players(settings, offset=0, limit=2)
    assert len(first.players) == 2
    assert first.total == 4
    assert first.has_next is True
    assert first.has_prev is False
    assert first.next_offset == 2

    second = list_players(settings, offset=2, limit=2)
    assert len(second.players) == 2
    assert second.has_next is False
    assert second.has_prev is True
    first_ids = [p.player_id for p in first.players]
    second_ids = [p.player_id for p in second.players]
    assert set(first_ids).isdisjoint(second_ids)


def test_player_card_seasons_label(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    page = list_players(settings)
    by_id = {p.player_id: p for p in page.players}
    assert by_id['00-0033873'].seasons_label == '2017–heute'
    assert by_id['00-0020531'].seasons_label == '2000–2022'


# ---------------------------------------------------------------------------
# Service: get_player_profile
# ---------------------------------------------------------------------------


def test_get_player_profile_missing_returns_none(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    assert get_player_profile(settings, 'NOPE') is None


def test_get_player_profile_case_insensitive_lookup(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    profile = get_player_profile(settings, '00-0033873'.lower())
    assert profile is not None
    assert profile.meta.player_id == '00-0033873'
    assert profile.meta.display_name == 'P.Mahomes'


def test_get_player_profile_enriches_team_name_via_join(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    profile = get_player_profile(settings, '00-0033873')
    assert profile is not None
    assert profile.meta.current_team_abbr == 'KC'
    assert profile.meta.current_team_name == 'Kansas City Chiefs'


def test_get_player_profile_career_and_meta_display(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_career(con, _sample_career_mahomes())
    finally:
        con.close()
    profile = get_player_profile(settings, '00-0033873')
    assert profile is not None
    assert profile.career is not None
    assert profile.career.seasons_played == 8
    assert profile.career.total_yards == 33400
    assert profile.career.span_label == '2017–2024'
    assert profile.meta.height_label == "6'2\""
    assert profile.meta.draft_label == '2017 · R1·P10 · KC'


def test_get_player_profile_career_missing_returns_none_slice(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    profile = get_player_profile(settings, '00-0033873')
    assert profile is not None
    assert profile.career is None
    assert profile.season_stats == ()
    assert profile.roster_history == ()


def test_get_player_profile_season_stats_desc(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_season_stats(con, _sample_season_stats_mahomes())
    finally:
        con.close()
    profile = get_player_profile(settings, '00-0033873')
    assert profile is not None
    assert [s.season for s in profile.season_stats] == [2024, 2023, 2022]
    assert profile.season_count == 3
    assert profile.season_stats[0].passing_tds == 30


def test_get_player_profile_roster_history_open_interval(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_roster_history(con, _sample_roster_history_mahomes())
    finally:
        con.close()
    profile = get_player_profile(settings, '00-0033873')
    assert profile is not None
    assert len(profile.roster_history) == 3
    # season DESC ordering: 2024, 2023, 2017
    seasons = [r.season for r in profile.roster_history]
    assert seasons == [2024, 2023, 2017]
    open_interval = profile.roster_history[0]
    assert open_interval.is_open is True
    assert open_interval.week_range_label == 'W1–offen'
    closed_interval = profile.roster_history[1]
    assert closed_interval.is_open is False
    assert closed_interval.week_range_label == 'W1–W17'
    assert profile.team_count == 1


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_players_page_lists_rows(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_team_overview(con, _sample_teams())
    finally:
        con.close()
    html = render_players_page(settings)
    assert 'data-testid="player-row"' in html
    assert 'P.Mahomes' in html
    assert 'T.Brady' in html
    assert 'href="/players/00-0033873"' in html


def test_render_players_page_empty_state(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_players_page(settings)
    assert 'Noch keine Spieler geladen' in html


def test_render_players_page_pagination_links(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    html = render_players_page(settings, offset=0, limit=2)
    assert 'data-testid="player-pagination"' in html
    assert 'offset=2' in html
    assert 'nächste →' in html


def test_render_player_profile_renders_all_sections(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
        _seed_team_overview(con, _sample_teams())
        _seed_career(con, _sample_career_mahomes())
        _seed_season_stats(con, _sample_season_stats_mahomes())
        _seed_roster_history(con, _sample_roster_history_mahomes())
    finally:
        con.close()
    html = render_player_profile_page(settings, '00-0033873')
    assert 'data-testid="player-header"' in html
    assert 'P.Mahomes' in html
    assert 'Kansas City Chiefs' in html
    assert 'data-testid="career-snapshot"' in html
    assert 'data-testid="player-season-row"' in html
    assert 'data-testid="player-roster-interval"' in html
    # Career totals rendered with number formatting (non-breaking space thousands).
    assert 'Total Yards' in html
    assert 'W1–offen' in html


def test_render_player_profile_not_found(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    html = render_player_profile_page(settings, 'NOPE')
    assert 'Spieler nicht gefunden' in html
    assert 'NOPE' in html


def test_render_player_profile_breadcrumb_and_active_nav(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_player_overview(con, _sample_players())
    finally:
        con.close()
    html = render_player_profile_page(settings, '00-0033873')
    assert 'href="/"' in html
    assert 'href="/players"' in html
    assert 'nav-link-active' in html
