from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import Settings
from new_nfl.web_preview import render_core_dictionary_preview


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


def test_render_core_dictionary_preview_writes_html(settings: Settings, tmp_path: Path) -> None:
    _prepare_core_table(settings)
    output = tmp_path / 'preview.html'

    result = render_core_dictionary_preview(
        settings,
        adapter_id='nflverse_bulk',
        output_path=str(output),
        limit=2,
    )

    assert result.adapter_id == 'nflverse_bulk'
    assert result.returned_row_count == 2
    assert output.exists()
    html = output.read_text(encoding='utf-8')
    assert 'NEW NFL Core Dictionary Preview' in html
    assert 'Summary by data type' in html
    assert 'game_id' in html


def test_render_core_dictionary_preview_respects_data_type_filter(settings: Settings, tmp_path: Path) -> None:
    _prepare_core_table(settings)
    output = tmp_path / 'preview_filtered.html'

    result = render_core_dictionary_preview(
        settings,
        adapter_id='nflverse_bulk',
        output_path=str(output),
        limit=10,
        data_type_filter='character',
    )

    assert result.match_row_count == 2
    html = output.read_text(encoding='utf-8')
    assert 'gameday' in html
    assert 'gametime' in html
    assert 'game_id' not in html
