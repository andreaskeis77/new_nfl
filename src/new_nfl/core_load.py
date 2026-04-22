from __future__ import annotations

from dataclasses import dataclass

import duckdb

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.adapters.slices import DEFAULT_SLICE_KEY, get_slice
from new_nfl.core.games import CoreGameLoadResult, execute_core_game_load
from new_nfl.core.players import CorePlayerLoadResult, execute_core_player_load
from new_nfl.core.teams import CoreTeamLoadResult, execute_core_team_load
from new_nfl.mart import build_schedule_field_dictionary_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings


@dataclass(frozen=True)
class CoreLoadResult:
    adapter_id: str
    pipeline_name: str
    run_mode: str
    run_status: str
    ingest_run_id: str
    source_schema: str
    source_object: str
    source_table: str
    target_schema: str
    target_object: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_key_count: int
    invalid_row_count: int
    load_event_id: str
    stage_dataset: str
    source_status: str
    mart_qualified_table: str
    mart_row_count: int


def _source_table_for_adapter(adapter_id: str) -> tuple[str, str]:
    if adapter_id != 'nflverse_bulk':
        raise ValueError(
            'T2.0A only supports adapter_id=nflverse_bulk for the first canonical dictionary slice'
        )
    return ('stg', 'nflverse_bulk_schedule_dictionary')


def _target_table_for_adapter(adapter_id: str) -> tuple[str, str]:
    if adapter_id != 'nflverse_bulk':
        raise ValueError(
            'T2.0A only supports adapter_id=nflverse_bulk for the first canonical dictionary slice'
        )
    return ('core', 'schedule_field_dictionary')


def _assert_required_columns(settings: Settings, source_table: str) -> None:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(f"DESCRIBE {source_table}").fetchall()
    finally:
        con.close()
    existing = {str(row[0]).strip().lower() for row in rows}
    required = {'field', 'data_type', 'description'}
    missing = sorted(required - existing)
    if missing:
        raise ValueError(
            f'{source_table} is missing required dictionary columns: {", ".join(missing)}'
        )


def _profile_source_table(settings: Settings, source_table: str) -> tuple[int, int, int]:
    _assert_required_columns(settings, source_table)
    con = duckdb.connect(str(settings.db_path))
    try:
        source_row_count = int(con.execute(f'SELECT COUNT(*) FROM {source_table}').fetchone()[0])
        distinct_key_count = int(
            con.execute(
                f"""
                SELECT COUNT(DISTINCT LOWER(TRIM(field)))
                FROM {source_table}
                WHERE NULLIF(TRIM(field), '') IS NOT NULL
                """
            ).fetchone()[0]
        )
        invalid_row_count = int(
            con.execute(
                f"""
                SELECT COUNT(*)
                FROM {source_table}
                WHERE NULLIF(TRIM(field), '') IS NULL
                """
            ).fetchone()[0]
        )
        return source_row_count, distinct_key_count, invalid_row_count
    finally:
        con.close()


def _rebuild_core_table(settings: Settings, source_table: str, qualified_table: str) -> int:
    _assert_required_columns(settings, source_table)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS core')
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {qualified_table} AS
            WITH ranked AS (
                SELECT
                    TRIM(field) AS field,
                    NULLIF(TRIM(data_type), '') AS data_type,
                    NULLIF(TRIM(description), '') AS description,
                    COALESCE(_source_file_id, '') AS _source_file_id,
                    COALESCE(_adapter_id, '') AS _adapter_id,
                    _loaded_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(field))
                        ORDER BY _loaded_at DESC NULLS LAST, _source_file_id DESC
                    ) AS _rn
                FROM {source_table}
                WHERE NULLIF(TRIM(field), '') IS NOT NULL
            )
            SELECT
                field,
                data_type,
                description,
                _source_file_id,
                _adapter_id,
                CURRENT_TIMESTAMP AS _canonicalized_at
            FROM ranked
            WHERE _rn = 1
            """
        )
        return int(con.execute(f'SELECT COUNT(*) FROM {qualified_table}').fetchone()[0])
    finally:
        con.close()


def execute_core_load(
    settings: Settings,
    *,
    adapter_id: str,
    execute: bool,
    slice_key: str = DEFAULT_SLICE_KEY,
) -> CoreLoadResult | CoreTeamLoadResult | CoreGameLoadResult | CorePlayerLoadResult:
    if slice_key != DEFAULT_SLICE_KEY:
        spec = get_slice(adapter_id, slice_key)
        if spec.core_table == 'core.team':
            return execute_core_team_load(settings, execute=execute)
        if spec.core_table == 'core.game':
            return execute_core_game_load(settings, execute=execute)
        if spec.core_table == 'core.player':
            return execute_core_player_load(settings, execute=execute)
        raise ValueError(
            f"No core-load promoter registered for slice "
            f"adapter_id={adapter_id} slice_key={slice_key}"
        )
    plan = build_adapter_plan(settings, adapter_id)
    source_schema, source_object = _source_table_for_adapter(adapter_id)
    source_table = f'{source_schema}.{source_object}'
    target_schema, target_object = _target_table_for_adapter(adapter_id)
    qualified_table = f'{target_schema}.{target_object}'
    pipeline_name = f'adapter.{adapter_id}.core_load'

    source_row_count, distinct_key_count, invalid_row_count = _profile_source_table(
        settings,
        source_table,
    )

    if not execute:
        return CoreLoadResult(
            adapter_id=adapter_id,
            pipeline_name=pipeline_name,
            run_mode='dry_run',
            run_status='planned_core_load',
            ingest_run_id='',
            source_schema=source_schema,
            source_object=source_object,
            source_table=source_table,
            target_schema=target_schema,
            target_object=target_object,
            qualified_table=qualified_table,
            source_row_count=source_row_count,
            row_count=0,
            distinct_key_count=distinct_key_count,
            invalid_row_count=invalid_row_count,
            load_event_id='',
            stage_dataset=plan.stage_dataset,
            source_status=plan.source_status,
            mart_qualified_table='',
            mart_row_count=0,
        )

    row_count = _rebuild_core_table(settings, source_table, qualified_table)
    mart_result = build_schedule_field_dictionary_v1(settings)
    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        adapter_id=adapter_id,
        run_mode='execute',
        run_status='core_dictionary_loaded',
        trigger_kind='cli',
        landing_dir='',
        manifest_path='',
        receipt_path='',
        asset_count=1,
        landed_file_count=1,
        message='T2.0A first canonical dictionary slice',
    )
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=adapter_id,
        pipeline_name=pipeline_name,
        event_kind='core_loaded',
        target_schema=target_schema,
        target_object=target_object,
        row_count=row_count,
        object_path=source_table,
        payload={
            'source_table': source_table,
            'qualified_table': qualified_table,
            'source_row_count': source_row_count,
            'distinct_key_count': distinct_key_count,
            'invalid_row_count': invalid_row_count,
            'row_count': row_count,
            'mart_qualified_table': mart_result.qualified_table,
            'mart_row_count': mart_result.row_count,
        },
    )
    return CoreLoadResult(
        adapter_id=adapter_id,
        pipeline_name=pipeline_name,
        run_mode='execute',
        run_status='core_dictionary_loaded',
        ingest_run_id=ingest_run_id,
        source_schema=source_schema,
        source_object=source_object,
        source_table=source_table,
        target_schema=target_schema,
        target_object=target_object,
        qualified_table=qualified_table,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_key_count=distinct_key_count,
        invalid_row_count=invalid_row_count,
        load_event_id=load_event_id,
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
        mart_qualified_table=mart_result.qualified_table,
        mart_row_count=mart_result.row_count,
    )
