from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import (
    finish_ingest_run,
    list_ingest_runs,
    list_load_events,
    record_load_event,
    start_ingest_run,
    upsert_pipeline_state,
)
from new_nfl.settings import Settings


@dataclass(frozen=True)
class AdapterExecutionResult:
    adapter_id: str
    pipeline_name: str
    ingest_run_id: str | None
    run_mode: str
    run_status: str
    landing_dir: str
    manifest_path: str | None
    receipt_path: str | None
    load_event_id: str | None
    landed_file_count: int
    asset_count: int
    stage_dataset: str
    source_status: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _planned_assets(adapter_id: str) -> list[dict[str, Any]]:
    if adapter_id == 'nflverse_bulk':
        return [
            {
                'asset_key': 'games',
                'source_ref': 'planned://nflverse/games',
                'format': 'parquet',
                'cadence': 'historical-plus-daily',
            },
            {
                'asset_key': 'rosters',
                'source_ref': 'planned://nflverse/rosters',
                'format': 'parquet',
                'cadence': 'daily',
            },
            {
                'asset_key': 'players',
                'source_ref': 'planned://nflverse/players',
                'format': 'parquet',
                'cadence': 'daily',
            },
            {
                'asset_key': 'player_stats',
                'source_ref': 'planned://nflverse/player_stats',
                'format': 'parquet',
                'cadence': 'daily-in-season',
            },
        ]
    return [
        {
            'asset_key': adapter_id,
            'source_ref': f'planned://{adapter_id}/placeholder',
            'format': 'json',
            'cadence': 'on-demand',
        }
    ]


def _build_landing_dir(settings: Settings, adapter_id: str, ingest_run_id: str) -> Path:
    return settings.raw_root / 'landed' / adapter_id / ingest_run_id


def _dry_run_landing_dir(settings: Settings, adapter_id: str) -> Path:
    return settings.raw_root / 'landed' / adapter_id / '<planned>'


def execute_adapter_contract(
    settings: Settings,
    adapter_id: str,
    *,
    execute: bool,
    triggered_by: str = 'cli',
) -> AdapterExecutionResult:
    bootstrap_local_environment(settings)
    plan = build_adapter_plan(settings, adapter_id)
    pipeline_name = f'adapter.{adapter_id}.fetch'
    assets = _planned_assets(adapter_id)

    if not execute:
        return AdapterExecutionResult(
            adapter_id=plan.adapter_id,
            pipeline_name=pipeline_name,
            ingest_run_id=None,
            run_mode='dry_run',
            run_status='planned',
            landing_dir=str(_dry_run_landing_dir(settings, adapter_id)),
            manifest_path=None,
            receipt_path=None,
            load_event_id=None,
            landed_file_count=0,
            asset_count=len(assets),
            stage_dataset=plan.stage_dataset,
            source_status=plan.source_status,
        )

    ingest_run_id = start_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        triggered_by=triggered_by,
        run_mode='execute',
        detail_json=json.dumps(
            {
                'adapter_id': adapter_id,
                'plan': plan.as_dict(),
                'asset_count': len(assets),
                'phase': 'T1.3',
            }
        ),
    )
    landing_dir = _build_landing_dir(settings, adapter_id, ingest_run_id)
    landing_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = landing_dir / 'request_manifest.json'
    receipt_path = landing_dir / 'fetch_receipt.json'

    manifest_payload = {
        'adapter_id': plan.adapter_id,
        'pipeline_name': pipeline_name,
        'run_mode': 'execute',
        'ingest_run_id': ingest_run_id,
        'generated_at_utc': _utc_timestamp(),
        'raw_landing_prefix': str(landing_dir),
        'stage_dataset': plan.stage_dataset,
        'source_status': plan.source_status,
        'asset_count': len(assets),
        'assets': assets,
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding='utf-8')

    load_event_detail = {
        'landing_dir': str(landing_dir),
        'manifest_path': str(manifest_path),
        'receipt_path': str(receipt_path),
        'adapter_id': plan.adapter_id,
        'asset_count': len(assets),
    }
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=plan.adapter_id,
        target_schema='raw',
        target_object=f'{plan.adapter_id}_contract_receipt',
        row_count=len(assets),
        event_status='landed_contract',
        detail_json=json.dumps(load_event_detail),
    )

    receipt_payload = {
        'adapter_id': plan.adapter_id,
        'pipeline_name': pipeline_name,
        'ingest_run_id': ingest_run_id,
        'run_status': 'landed_contract',
        'recorded_at_utc': _utc_timestamp(),
        'load_event_id': load_event_id,
        'landed_files': [manifest_path.name, receipt_path.name],
        'asset_count': len(assets),
        'stage_dataset': plan.stage_dataset,
        'source_status': plan.source_status,
    }
    receipt_path.write_text(json.dumps(receipt_payload, indent=2), encoding='utf-8')

    finish_ingest_run(
        settings,
        ingest_run_id=ingest_run_id,
        run_status='landed_contract',
        detail_json=json.dumps(receipt_payload),
    )
    upsert_pipeline_state(
        settings,
        pipeline_name=pipeline_name,
        last_run_status='landed_contract',
        state_json=json.dumps(
            {
                'adapter_id': plan.adapter_id,
                'ingest_run_id': ingest_run_id,
                'landing_dir': str(landing_dir),
                'manifest_path': str(manifest_path),
                'receipt_path': str(receipt_path),
                'asset_count': len(assets),
            }
        ),
        mark_success=True,
    )

    return AdapterExecutionResult(
        adapter_id=plan.adapter_id,
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        run_mode='execute',
        run_status='landed_contract',
        landing_dir=str(landing_dir),
        manifest_path=str(manifest_path),
        receipt_path=str(receipt_path),
        load_event_id=load_event_id,
        landed_file_count=2,
        asset_count=len(assets),
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
    )


def latest_adapter_run_summary(settings: Settings, adapter_id: str) -> dict[str, Any] | None:
    pipeline_name = f'adapter.{adapter_id}.fetch'
    runs = list_ingest_runs(settings, pipeline_name=pipeline_name)
    if not runs:
        return None
    latest_run = runs[0]
    load_events = list_load_events(settings, ingest_run_id=str(latest_run['ingest_run_id']))
    return {
        'pipeline_name': pipeline_name,
        'latest_run': latest_run,
        'load_event_count': len(load_events),
    }
