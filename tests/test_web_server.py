from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import Settings
from new_nfl.web_server import (
    build_health_url,
    build_preview_url,
    build_web_preview_html,
)


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


def _prepare_core_table(settings: Settings) -> None:
    from new_nfl.mart import build_schedule_field_dictionary_v1

    bootstrap_local_environment(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS core')
        con.execute(
            '''
            CREATE OR REPLACE TABLE core.schedule_field_dictionary (
                field VARCHAR,
                data_type VARCHAR,
                description VARCHAR
            )
            '''
        )
        con.executemany(
            'INSERT INTO core.schedule_field_dictionary VALUES (?, ?, ?)',
            [
                ('game_id', 'numeric', 'Primary game identifier.'),
                ('gameday', 'character', 'Date of the game.'),
                ('gametime', 'character', 'Time of the game.'),
            ],
        )
    finally:
        con.close()
    build_schedule_field_dictionary_v1(settings)


def test_build_web_preview_html_contains_expected_sections(settings: Settings) -> None:
    _prepare_core_table(settings)

    html = build_web_preview_html(settings, adapter_id='nflverse_bulk', limit=2)

    assert 'NEW NFL Core Dictionary Preview' in html
    assert 'Summary by data type' in html
    assert 'Preview rows' in html
    assert 'game_id' in html


def test_build_web_preview_html_respects_data_type_filter(settings: Settings) -> None:
    _prepare_core_table(settings)

    html = build_web_preview_html(
        settings,
        adapter_id='nflverse_bulk',
        limit=10,
        data_type_filter='character',
    )

    assert 'gameday' in html
    assert 'gametime' in html
    assert 'game_id' not in html


def test_build_preview_urls() -> None:
    assert build_preview_url('127.0.0.1', 8787) == 'http://127.0.0.1:8787/'
    assert build_health_url('127.0.0.1', 8787) == 'http://127.0.0.1:8787/healthz'
