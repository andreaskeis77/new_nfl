from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import create_ingest_run, record_source_file, seed_default_sources
from new_nfl.settings import load_settings
from new_nfl.source_files import list_source_files


def _register_source_file(
    settings,
    adapter_id: str,
    payload_path: Path,
    *,
    source_url: str,
    created_at: str,
) -> str:
    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=f'adapter.{adapter_id}.remote_fetch',
        adapter_id=adapter_id,
        run_mode='execute',
        run_status='remote_fetched',
        trigger_kind='test',
        landing_dir=str(payload_path.parent),
        manifest_path='',
        receipt_path='',
        asset_count=1,
        landed_file_count=1,
        message='test source file registration',
    )
    source_file_id = record_source_file(
        settings,
        ingest_run_id=ingest_run_id,
        adapter_id=adapter_id,
        source_url=source_url,
        local_path=str(payload_path),
        file_size_bytes=payload_path.stat().st_size,
        sha256_hex=f'sha-{payload_path.stem}',
    )
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute(
            'UPDATE meta.source_files SET created_at = CAST(? AS TIMESTAMP) WHERE source_file_id = ?',
            [created_at, source_file_id],
        )
    finally:
        con.close()
    return source_file_id


def test_list_source_files_returns_newest_first_and_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    older = tmp_path / 'older.csv'
    newer = tmp_path / 'newer.csv'
    older.write_text('a\n1\n', encoding='utf-8')
    newer.write_text('a\n2\n', encoding='utf-8')

    older_id = _register_source_file(
        settings,
        'nflverse_bulk',
        older,
        source_url='https://example.invalid/older.csv',
        created_at='2026-03-29 10:00:00',
    )
    newer_id = _register_source_file(
        settings,
        'nflverse_bulk',
        newer,
        source_url='https://example.invalid/newer.csv',
        created_at='2026-03-29 11:00:00',
    )

    result = list_source_files(settings, adapter_id='nflverse_bulk', limit=1)

    assert result.adapter_id == 'nflverse_bulk'
    assert result.total_row_count == 2
    assert result.returned_row_count == 1
    assert result.limit == 1
    assert result.rows[0][0] == newer_id
    assert result.rows[0][2].endswith('newer.csv')
    assert older_id != newer_id


def test_list_source_files_returns_empty_when_no_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    result = list_source_files(settings, adapter_id='nflverse_bulk', limit=20)

    assert result.total_row_count == 0
    assert result.returned_row_count == 0
    assert result.rows == ()


def test_list_source_files_rejects_non_positive_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    with pytest.raises(ValueError, match='limit must be >= 1'):
        list_source_files(settings, adapter_id='nflverse_bulk', limit=0)
