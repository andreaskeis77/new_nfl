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
    )

    assert result.qualified_table == 'core.schedule_field_dictionary'
    assert result.total_row_count == 3
    assert result.match_row_count == 3
    assert result.returned_row_count == 3
    assert result.rows[0][0] == 'away_team'
    assert result.rows[1][0] == 'game_id'
    assert result.rows[2][0] == 'home_team'


def test_browse_core_dictionary_applies_prefix_filter(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = browse_core_dictionary(
        settings,
        adapter_id='nflverse_bulk',
        limit=10,
        field_prefix='ho',
    )

    assert result.total_row_count == 3
    assert result.match_row_count == 1
    assert result.returned_row_count == 1
    assert result.field_prefix == 'ho'
    assert result.rows == (('home_team', 'character', 'Home team abbreviation'),)


def test_browse_core_dictionary_requires_existing_table(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    with pytest.raises(ValueError, match='does not exist; run core-load'):
        browse_core_dictionary(
            settings,
            adapter_id='nflverse_bulk',
            limit=10,
            field_prefix='',
        )
