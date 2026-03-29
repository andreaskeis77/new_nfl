from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core_browse import browse_core_dictionary
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


def _prepare_core_table(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS core')
        con.execute(
            """
            CREATE OR REPLACE TABLE core.schedule_field_dictionary (
                field VARCHAR,
                data_type VARCHAR,
                description VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        con.executemany(
            """
            INSERT INTO core.schedule_field_dictionary (
                field,
                data_type,
                description,
                _source_file_id,
                _adapter_id,
                _loaded_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                ('away_team', 'character', 'Away team abbreviation', 'sf-1', 'nflverse_bulk'),
                ('game_id', 'numeric', 'Game identifier', 'sf-1', 'nflverse_bulk'),
                ('home_team', 'character', 'Home team abbreviation', 'sf-1', 'nflverse_bulk'),
            ],
        )
    finally:
        con.close()


def test_browse_core_dictionary_returns_sorted_rows(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = browse_core_dictionary(
        settings,
        adapter_id='nflverse_bulk',
        limit=10,
        field_prefix='',
        data_type_filter='',
    )

    assert result.qualified_table == 'core.schedule_field_dictionary'
    assert result.total_row_count == 3
    assert result.match_row_count == 3
    assert result.returned_row_count == 3
    assert result.rows == (
        ('away_team', 'character', 'Away team abbreviation'),
        ('game_id', 'numeric', 'Game identifier'),
        ('home_team', 'character', 'Home team abbreviation'),
    )
    assert result.data_type_filter == ''


def test_browse_core_dictionary_filters_by_prefix(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = browse_core_dictionary(
        settings,
        adapter_id='nflverse_bulk',
        limit=10,
        field_prefix='ga',
        data_type_filter='',
    )

    assert result.match_row_count == 1
    assert result.rows == (('game_id', 'numeric', 'Game identifier'),)


def test_browse_core_dictionary_filters_by_data_type(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = browse_core_dictionary(
        settings,
        adapter_id='nflverse_bulk',
        limit=10,
        field_prefix='',
        data_type_filter='character',
    )

    assert result.match_row_count == 2
    assert result.returned_row_count == 2
    assert result.data_type_filter == 'character'
    assert result.rows == (
        ('away_team', 'character', 'Away team abbreviation'),
        ('home_team', 'character', 'Home team abbreviation'),
    )


def test_browse_core_dictionary_combines_prefix_and_data_type_filter(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = browse_core_dictionary(
        settings,
        adapter_id='nflverse_bulk',
        limit=10,
        field_prefix='g',
        data_type_filter='numeric',
    )

    assert result.match_row_count == 1
    assert result.rows == (('game_id', 'numeric', 'Game identifier'),)


def test_browse_core_dictionary_rejects_limit_below_one(settings: Settings) -> None:
    _prepare_core_table(settings)

    with pytest.raises(ValueError, match='limit must be >= 1'):
        browse_core_dictionary(
            settings,
            adapter_id='nflverse_bulk',
            limit=0,
            field_prefix='',
            data_type_filter='',
        )
