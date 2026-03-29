
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core_summary import summarize_core_dictionary
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
                description VARCHAR
            )
            """
        )
        con.executemany(
            """
            INSERT INTO core.schedule_field_dictionary (field, data_type, description)
            VALUES (?, ?, ?)
            """,
            [
                ('game_id', 'numeric', 'game id'),
                ('gameday', 'character', 'game day'),
                ('week', 'numeric', 'week number'),
                ('game_type', 'character', 'game type'),
                ('spread_line', 'numeric', 'spread'),
            ],
        )
    finally:
        con.close()


def test_summarize_core_dictionary_returns_grouped_counts(settings: Settings) -> None:
    _prepare_core_table(settings)

    result = summarize_core_dictionary(settings, adapter_id='nflverse_bulk')

    assert result.adapter_id == 'nflverse_bulk'
    assert result.qualified_table == 'core.schedule_field_dictionary'
    assert result.total_row_count == 5
    assert result.distinct_data_type_count == 2
    assert result.data_type_rows == (
        ('character', 2),
        ('numeric', 3),
    )


def test_summarize_core_dictionary_rejects_unsupported_adapter(settings: Settings) -> None:
    _prepare_core_table(settings)

    with pytest.raises(ValueError, match='only supports adapter_id=nflverse_bulk'):
        summarize_core_dictionary(settings, adapter_id='unsupported_adapter')
