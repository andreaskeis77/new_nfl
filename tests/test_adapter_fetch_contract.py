from __future__ import annotations

import json
from pathlib import Path

from new_nfl.adapters import execute_adapter_contract
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import (
    get_pipeline_state,
    list_ingest_runs,
    list_load_events,
    seed_default_sources,
)
from new_nfl.settings import load_settings


def test_run_adapter_dry_run_has_no_landed_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    result = execute_adapter_contract(settings, 'nflverse_bulk', execute=False)

    assert result.run_mode == 'dry_run'
    assert result.run_status == 'planned'
    assert result.ingest_run_id is None
    assert result.manifest_path is None
    assert result.receipt_path is None
    assert result.asset_count == 4
    assert not (settings.raw_root / 'landed' / 'nflverse_bulk').exists()


def test_run_adapter_execute_writes_receipt_and_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    result = execute_adapter_contract(settings, 'nflverse_bulk', execute=True)

    assert result.run_mode == 'execute'
    assert result.run_status == 'landed_contract'
    assert result.ingest_run_id is not None
    assert result.load_event_id is not None
    assert result.landed_file_count == 2

    manifest_path = Path(result.manifest_path or '')
    receipt_path = Path(result.receipt_path or '')

    assert manifest_path.exists()
    assert receipt_path.exists()

    manifest_payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    receipt_payload = json.loads(receipt_path.read_text(encoding='utf-8'))

    assert manifest_payload['adapter_id'] == 'nflverse_bulk'
    assert manifest_payload['asset_count'] == 4
    assert receipt_payload['run_status'] == 'landed_contract'
    assert receipt_payload['load_event_id'] == result.load_event_id

    state = get_pipeline_state(settings, 'adapter.nflverse_bulk.fetch')
    assert state is not None
    assert state['last_run_status'] == 'landed_contract'

    runs = list_ingest_runs(settings, pipeline_name='adapter.nflverse_bulk.fetch')
    assert len(runs) == 1
    assert runs[0]['ingest_run_id'] == result.ingest_run_id
    assert runs[0]['run_status'] == 'landed_contract'

    load_events = list_load_events(settings, ingest_run_id=result.ingest_run_id)
    assert len(load_events) == 1
    assert load_events[0]['source_id'] == 'nflverse_bulk'
    assert load_events[0]['event_status'] == 'landed_contract'
