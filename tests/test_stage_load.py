from __future__ import annotations

from pathlib import Path

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import create_ingest_run, record_source_file, seed_default_sources
from new_nfl.settings import load_settings
from new_nfl.stage_load import execute_stage_load


def _register_csv_source_file(settings, adapter_id: str, csv_path: Path) -> str:
    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=f'adapter.{adapter_id}.remote_fetch',
        adapter_id=adapter_id,
        run_mode='execute',
        run_status='remote_fetched',
        trigger_kind='test',
        landing_dir=str(csv_path.parent),
        manifest_path='',
        receipt_path='',
        asset_count=1,
        landed_file_count=1,
        message='test source file registration',
    )
    return record_source_file(
        settings,
        ingest_run_id=ingest_run_id,
        adapter_id=adapter_id,
        source_url=f'https://example.invalid/{csv_path.name}',
        local_path=str(csv_path),
        file_size_bytes=csv_path.stat().st_size,
        sha256_hex='abc123',
    )


def test_stage_load_dry_run_reports_target_table(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    payload = tmp_path / 'payload.csv'
    payload.write_text('season,week\n2025,1\n', encoding='utf-8')
    source_file_id = _register_csv_source_file(settings, 'nflverse_bulk', payload)

    result = execute_stage_load(settings, adapter_id='nflverse_bulk', execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned_stage_load'
    assert result.source_file_id == source_file_id
    assert result.qualified_table == 'stg.nflverse_bulk_payload'


def test_stage_load_execute_creates_stage_table(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    payload = tmp_path / 'dictionary_schedules.csv'
    payload.write_text('season,week\n2025,1\n', encoding='utf-8')
    source_file_id = _register_csv_source_file(settings, 'nflverse_bulk', payload)

    result = execute_stage_load(settings, adapter_id='nflverse_bulk', execute=True)

    assert result.run_status == 'staged_csv_loaded'
    assert result.source_file_id == source_file_id
    assert result.qualified_table == 'stg.nflverse_bulk_schedule_dictionary'
    assert result.row_count == 1
    assert result.load_event_id

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            'SELECT season, week, _source_file_id, _adapter_id '
            'FROM stg.nflverse_bulk_schedule_dictionary'
        ).fetchone()
    finally:
        con.close()

    assert row == ('2025', '1', source_file_id, 'nflverse_bulk')


def test_stage_load_can_pin_specific_source_file_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    older = tmp_path / 'payload_old.csv'
    older.write_text('season,week\n2020,3\n', encoding='utf-8')
    older_source_file_id = _register_csv_source_file(settings, 'nflverse_bulk', older)

    newer = tmp_path / 'payload_new.csv'
    newer.write_text('season,week\n2025,9\n', encoding='utf-8')
    _register_csv_source_file(settings, 'nflverse_bulk', newer)

    result = execute_stage_load(
        settings,
        adapter_id='nflverse_bulk',
        execute=True,
        source_file_id=older_source_file_id,
    )

    assert result.source_file_id == older_source_file_id
    assert result.qualified_table == 'stg.nflverse_bulk_payload_old'
    assert result.row_count == 1

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            'SELECT season, week, _source_file_id, _adapter_id '
            'FROM stg.nflverse_bulk_payload_old'
        ).fetchone()
    finally:
        con.close()

    assert row == ('2020', '3', older_source_file_id, 'nflverse_bulk')
