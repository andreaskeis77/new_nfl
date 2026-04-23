"""T2.6C — Season/Week/Game drilldown views (ADR-0029).

Exercises the read service over ``mart.game_overview_v1`` and the three
rendered pages (``/seasons``, ``/seasons/<s>``, ``/seasons/<s>/weeks/<w>``).
Tests seed the mart directly so they do not depend on the core-load path.
"""
from __future__ import annotations

from datetime import date

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings
from new_nfl.web.games_view import (
    list_games,
    list_seasons,
    list_weeks,
)
from new_nfl.web.renderer import (
    render_season_weeks_page,
    render_seasons_page,
    render_week_games_page,
)


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_mart(settings, rows):
    con = duckdb.connect(str(settings.db_path))
    try:
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
                   home_score, away_score, stadium, is_completed, winner_team)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                row,
            )
    finally:
        con.close()


def _sample_rows() -> list[tuple]:
    return [
        # (game_id, season, week, gameday, gametime, home, away,
        #  home_score, away_score, stadium, is_completed, winner_team)
        ('2024_01_BAL_KC', 2024, 1, date(2024, 9, 5), '20:20',
         'KC', 'BAL', 27, 20, 'GEHA Field', True, 'KC'),
        ('2024_01_GB_PHI', 2024, 1, date(2024, 9, 6), '20:15',
         'PHI', 'GB', 34, 29, 'Lincoln Financial', True, 'PHI'),
        ('2024_02_LAR_ARI', 2024, 2, date(2024, 9, 15), '16:05',
         'ARI', 'LAR', 41, 10, 'State Farm Stadium', True, 'ARI'),
        ('2024_02_BUF_MIA', 2024, 2, date(2024, 9, 12), '20:15',
         'MIA', 'BUF', None, None, 'Hard Rock Stadium', False, None),
        ('2023_01_DET_KC', 2023, 1, date(2023, 9, 7), '20:20',
         'KC', 'DET', 20, 21, 'GEHA Field', True, 'DET'),
    ]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def test_list_seasons_empty_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    assert list_seasons(settings) == ()


def test_list_seasons_returns_descending_with_counts(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    seasons = list_seasons(settings)
    assert [s.season for s in seasons] == [2024, 2023]
    assert seasons[0].game_count == 4
    assert seasons[0].completed_count == 3
    assert seasons[0].min_week == 1
    assert seasons[0].max_week == 2
    assert seasons[0].is_complete is False
    assert seasons[1].game_count == 1
    assert seasons[1].is_complete is True


def test_list_weeks_filters_by_season(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    weeks = list_weeks(settings, 2024)
    assert [w.week for w in weeks] == [1, 2]
    week_one = weeks[0]
    assert week_one.game_count == 2
    assert week_one.completed_count == 2
    assert week_one.earliest_gameday == date(2024, 9, 5)
    assert week_one.is_complete is True
    week_two = weeks[1]
    assert week_two.completed_count == 1
    assert week_two.is_complete is False


def test_list_games_orders_by_gameday_then_home(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    games = list_games(settings, 2024, 1)
    assert len(games) == 2
    assert games[0].game_id == '2024_01_BAL_KC'
    assert games[0].score_label == '20 – 27'
    assert games[0].status == 'final'
    assert games[0].label == 'BAL @ KC'
    assert games[1].game_id == '2024_01_GB_PHI'


def test_list_games_empty_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    assert list_games(settings, 2024, 1) == ()


def test_list_games_renders_score_dash_for_unplayed(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    games = list_games(settings, 2024, 2)
    unplayed = [g for g in games if not g.is_completed]
    assert unplayed, 'fixture must include one unplayed game'
    assert unplayed[0].score_label == '—'
    assert unplayed[0].status == 'scheduled'


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_seasons_page_lists_all_seasons(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_seasons_page(settings)
    assert 'Seasons' in html
    assert '2024' in html
    assert '2023' in html
    assert 'Wochen öffnen' in html
    assert 'href="/seasons/2024"' in html


def test_render_seasons_page_empty_state_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_seasons_page(settings)
    assert 'Noch keine Seasons geladen' in html


def test_render_season_weeks_page_shows_week_rows(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_season_weeks_page(settings, 2024)
    assert 'Season 2024' in html
    assert 'W01' in html
    assert 'W02' in html
    assert 'href="/seasons/2024/weeks/1"' in html
    assert '2024-09-05' in html


def test_render_season_weeks_page_empty_state_when_no_games(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_season_weeks_page(settings, 1999)
    assert 'Keine Wochen gefunden' in html


def test_render_week_games_page_shows_game_rows(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_week_games_page(settings, 2024, 1)
    assert 'data-game-id="2024_01_BAL_KC"' in html
    assert 'data-game-id="2024_01_GB_PHI"' in html
    assert '20 – 27' in html
    assert 'GEHA Field' in html
    assert 'Final' in html


def test_render_week_games_page_shows_scheduled_badge_for_unplayed(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_week_games_page(settings, 2024, 2)
    assert 'geplant' in html


def test_render_week_games_page_empty_state_when_week_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_week_games_page(settings, 2024, 99)
    assert 'Keine Spiele in dieser Woche' in html


def test_breadcrumb_chain_for_week_view(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_week_games_page(settings, 2024, 1)
    assert 'href="/"' in html
    assert 'href="/seasons"' in html
    assert 'href="/seasons/2024"' in html
    assert 'aria-current="page"' in html


def test_week_view_active_nav_is_seasons(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_mart(settings, _sample_rows())
    html = render_week_games_page(settings, 2024, 1)
    assert 'nav-link-active' in html
