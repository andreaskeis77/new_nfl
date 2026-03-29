from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import new_nfl.cli as cli_module
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import create_ingest_run, record_source_file, seed_default_sources
from new_nfl.settings import load_settings


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


def test_build_parser_accepts_list_source_files_command() -> None:
    parser = cli_module.build_parser()

    args = parser.parse_args(['list-source-files', '--adapter-id', 'nflverse_bulk'])

    assert args.command == 'list-source-files'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.limit == 20


def test_build_parser_accepts_list_source_files_limit() -> None:
    parser = cli_module.build_parser()

    args = parser.parse_args(
        ['list-source-files', '--adapter-id', 'nflverse_bulk', '--limit', '5']
    )

    assert args.command == 'list-source-files'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.limit == 5


def test_cmd_list_source_files_prints_rows(settings_tmp_path, monkeypatch, capsys) -> None:
    settings = settings_tmp_path
    payload = settings.repo_root / 'payload.csv'
    payload.write_text('a\n1\n', encoding='utf-8')

    _register_source_file(
        settings,
        'nflverse_bulk',
        payload,
        source_url='https://example.invalid/payload.csv',
        created_at='2026-03-29 10:00:00',
    )
    monkeypatch.setattr(cli_module, 'load_settings', lambda: settings)

    exit_code = cli_module._cmd_list_source_files('nflverse_bulk', 20)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert 'ADAPTER_ID=nflverse_bulk' in out
    assert 'TOTAL_ROW_COUNT=1' in out
    assert 'RETURNED_ROW_COUNT=1' in out
    assert 'SOURCE_FILE_ROW=' in out
    assert 'payload.csv' in out


@pytest.fixture()
def settings_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    return settings
