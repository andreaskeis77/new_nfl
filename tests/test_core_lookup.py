from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core_lookup import lookup_core_dictionary_field
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
            '''
            CREATE OR REPLACE TABLE core.schedule_field_dictionary (
                field VARCHAR,
                data_type VARCHAR,
                description VARCHAR,
                _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        con.execute(
            '''
            INSERT INTO core.schedule_field_dictionary (field, data_type, description)
            VALUES
                ('game_id', 'numeric', 'Primary game identifier'),
                ('gameday', 'character', 'Game date'),
                ('home_team', 'character', 'Home team code')
            '''
        )
    finally:
        con.close()


def test_lookup_core_dictionary_field_returns_exact_match(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = lookup_core_dictionary_field(
        settings,
        adapter_id='nflverse_bulk',
        field='game_id',
    )

    assert result.found is True
    assert result.field == 'game_id'
    assert result.data_type == 'numeric'
    assert result.description == 'Primary game identifier'
    assert result.qualified_table == 'core.schedule_field_dictionary'


def test_lookup_core_dictionary_field_normalizes_whitespace_and_case(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = lookup_core_dictionary_field(
        settings,
        adapter_id='nflverse_bulk',
        field='  GAMEDAY  ',
    )

    assert result.found is True
    assert result.field == 'gameday'
    assert result.data_type == 'character'


def test_lookup_core_dictionary_field_returns_not_found(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = lookup_core_dictionary_field(
        settings,
        adapter_id='nflverse_bulk',
        field='does_not_exist',
    )

    assert result.found is False
    assert result.field == ''
    assert result.data_type == ''
    assert result.description == ''


def test_lookup_core_dictionary_field_rejects_unsupported_adapter(settings: Settings) -> None:
    _prepare_core_table(settings)

    with pytest.raises(ValueError, match='only supports adapter_id=nflverse_bulk'):
        lookup_core_dictionary_field(
            settings,
            adapter_id='unsupported_adapter',
            field='game_id',
        )
