from __future__ import annotations

import sys
from pathlib import Path

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import create_ingest_run, record_source_file, seed_default_sources
from new_nfl.settings import load_settings


def _register_csv_source_file(settings, adapter_id: str, csv_path: Path) -> None:
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
    record_source_file(
        settings,
        ingest_run_id=ingest_run_id,
        adapter_id=adapter_id,
        source_url='https://example.invalid/dictionary_schedules.csv',
        local_path=str(csv_path),
        file_size_bytes=csv_path.stat().st_size,
        sha256_hex='abc123',
    )


def test_cli_stage_load_execute(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    payload = tmp_path / 'dictionary_schedules.csv'
    payload.write_text('season,week\n2025,1\n', encoding='utf-8')
    _register_csv_source_file(settings, 'nflverse_bulk', payload)

    from new_nfl.cli import main

    monkeypatch.setattr(
        sys,
        'argv',
        ['new-nfl', 'stage-load', '--adapter-id', 'nflverse_bulk', '--execute'],
    )
    rc = main()

    out = capsys.readouterr().out
    assert rc == 0
    assert 'RUN_STATUS=staged_csv_loaded' in out
    assert 'QUALIFIED_TABLE=stg.nflverse_bulk_schedule_dictionary' in out
