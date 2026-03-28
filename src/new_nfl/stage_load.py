from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.metadata import (
    create_ingest_run,
    latest_source_file,
    load_csv_into_stage_table,
    record_load_event,
)
from new_nfl.settings import Settings


@dataclass(frozen=True)
class StageLoadResult:
    adapter_id: str
    pipeline_name: str
    run_mode: str
    run_status: str
    ingest_run_id: str
    source_file_id: str
    source_file_path: str
    target_schema: str
    target_object: str
    qualified_table: str
    row_count: int
    load_event_id: str
    stage_dataset: str
    source_status: str


def _target_object_for_file(adapter_id: str, filename: str) -> str:
    name = Path(filename).stem.strip().lower().replace('-', '_')
    if adapter_id == 'nflverse_bulk' and name == 'dictionary_schedules':
        return 'nflverse_bulk_schedule_dictionary'
    return f'{adapter_id}_{name}'


def execute_stage_load(
    settings: Settings,
    *,
    adapter_id: str,
    execute: bool,
) -> StageLoadResult:
    plan = build_adapter_plan(settings, adapter_id)
    source_file = latest_source_file(settings, adapter_id)
    if source_file is None:
        raise ValueError(f'No source file recorded for adapter_id={adapter_id}')

    source_file_id = str(source_file['source_file_id'])
    source_file_path = str(source_file['local_path'])
    target_schema = 'stg'
    target_object = _target_object_for_file(adapter_id, Path(source_file_path).name)
    qualified_table = f'{target_schema}.{target_object}'
    pipeline_name = f'adapter.{adapter_id}.stage_load'

    if not execute:
        return StageLoadResult(
            adapter_id=adapter_id,
            pipeline_name=pipeline_name,
            run_mode='dry_run',
            run_status='planned_stage_load',
            ingest_run_id='',
            source_file_id=source_file_id,
            source_file_path=source_file_path,
            target_schema=target_schema,
            target_object=target_object,
            qualified_table=qualified_table,
            row_count=0,
            load_event_id='',
            stage_dataset=plan.stage_dataset,
            source_status=plan.source_status,
        )

    row_count = load_csv_into_stage_table(
        settings,
        csv_path=source_file_path,
        qualified_table=qualified_table,
        source_file_id=source_file_id,
        adapter_id=adapter_id,
    )
    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        adapter_id=adapter_id,
        run_mode='execute',
        run_status='staged_csv_loaded',
        trigger_kind='cli',
        landing_dir='',
        manifest_path='',
        receipt_path='',
        asset_count=1,
        landed_file_count=1,
        message='T1.5 first normalized staging load',
    )
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=adapter_id,
        pipeline_name=pipeline_name,
        event_kind='stage_loaded',
        target_schema=target_schema,
        target_object=target_object,
        row_count=row_count,
        object_path=source_file_path,
        payload={
            'source_file_id': source_file_id,
            'qualified_table': qualified_table,
            'row_count': row_count,
        },
    )
    return StageLoadResult(
        adapter_id=adapter_id,
        pipeline_name=pipeline_name,
        run_mode='execute',
        run_status='staged_csv_loaded',
        ingest_run_id=ingest_run_id,
        source_file_id=source_file_id,
        source_file_path=source_file_path,
        target_schema=target_schema,
        target_object=target_object,
        qualified_table=qualified_table,
        row_count=row_count,
        load_event_id=load_event_id,
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
    )
