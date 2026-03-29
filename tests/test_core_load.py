from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core_load import execute_core_load
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


def _prepare_stage_table(
    settings: Settings,
    rows: list[tuple[str | None, str | None, str | None, str | None, str | None]],
) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            """
            CREATE OR REPLACE TABLE stg.nflverse_bulk_schedule_dictionary (
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
            INSERT INTO stg.nflverse_bulk_schedule_dictionary (
                field,
                data_type,
                description,
                _source_file_id,
                _adapter_id,
                _loaded_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            rows,
        )
    finally:
        con.close()


def test_execute_core_load_dry_run_profiles_dictionary_source(settings: Settings) -> None:
    _prepare_stage_table(
        settings,
        [
            ('game_id', 'numeric', 'Game identifier', 'sf-1', 'nflverse_bulk'),
            ('season', 'numeric', 'Season year', 'sf-1', 'nflverse_bulk'),
            ('season', 'numeric', 'Season year duplicate', 'sf-2', 'nflverse_bulk'),
            ('', 'character', 'invalid blank key', 'sf-3', 'nflverse_bulk'),
        ],
    )

    result = execute_core_load(settings, adapter_id='nflverse_bulk', execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_core_load'
    assert result.source_table == 'stg.nflverse_bulk_schedule_dictionary'
    assert result.qualified_table == 'core.schedule_field_dictionary'
    assert result.source_row_count == 4
    assert result.distinct_key_count == 2
    assert result.invalid_row_count == 1
    assert result.row_count == 0


def test_execute_core_load_execute_rebuilds_dictionary_core_table(settings: Settings) -> None:
    _prepare_stage_table(
        settings,
        [
            ('game_id', 'numeric', 'Game identifier', 'sf-1', 'nflverse_bulk'),
            ('season', 'numeric', 'Season year', 'sf-1', 'nflverse_bulk'),
            ('season', 'numeric', 'Season year duplicate', 'sf-2', 'nflverse_bulk'),
            ('week', 'numeric', 'Week number', 'sf-1', 'nflverse_bulk'),
            (None, 'character', 'invalid null key', 'sf-3', 'nflverse_bulk'),
        ],
    )

    result = execute_core_load(settings, adapter_id='nflverse_bulk', execute=True)

    assert result.run_mode == 'execute'
    assert result.run_status == 'core_dictionary_loaded'
    assert result.row_count == 3
    assert result.distinct_key_count == 3
    assert result.invalid_row_count == 1
    assert result.ingest_run_id
    assert result.load_event_id

    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            """
            SELECT field, data_type, description, _source_file_id, _adapter_id
            FROM core.schedule_field_dictionary
            ORDER BY field
            """
        ).fetchall()
    finally:
        con.close()

    assert rows == [
        ('game_id', 'numeric', 'Game identifier', 'sf-1', 'nflverse_bulk'),
        ('season', 'numeric', 'Season year duplicate', 'sf-2', 'nflverse_bulk'),
        ('week', 'numeric', 'Week number', 'sf-1', 'nflverse_bulk'),
    ]


def test_execute_core_load_requires_dictionary_columns(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            """
            CREATE OR REPLACE TABLE stg.nflverse_bulk_schedule_dictionary (
                foo VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
    finally:
        con.close()

    with pytest.raises(ValueError, match='missing required dictionary columns'):
        execute_core_load(settings, adapter_id='nflverse_bulk', execute=False)
