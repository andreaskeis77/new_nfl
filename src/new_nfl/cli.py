from __future__ import annotations

import argparse

from new_nfl.adapters import (
    build_adapter_plan,
    execute_fetch_contract,
    execute_remote_fetch,
    get_adapter_descriptor,
    list_adapter_descriptors,
)
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core_browse import browse_core_dictionary
from new_nfl.core_load import execute_core_load
from new_nfl.core_lookup import lookup_core_dictionary_field
from new_nfl.core_summary import summarize_core_dictionary
from new_nfl.jobs import (
    describe_job,
    list_jobs,
    register_job,
    register_retry_policy,
)
from new_nfl.metadata import (
    get_pipeline_state,
    list_ingest_runs,
    list_sources,
    seed_default_sources,
    upsert_pipeline_state,
)
from new_nfl.settings import load_settings
from new_nfl.source_files import list_source_files
from new_nfl.stage_load import execute_stage_load
from new_nfl.web_preview import render_core_dictionary_preview
from new_nfl.web_server import serve_web_preview


def _cmd_bootstrap() -> int:
    settings = load_settings()
    db_path = bootstrap_local_environment(settings)
    print(f'ENV={settings.env}')
    print(f'REPO_ROOT={settings.repo_root}')
    print(f'DATA_ROOT={settings.data_root}')
    print(f'DB_PATH={db_path}')
    print('BOOTSTRAP=OK')
    return 0


def _cmd_health() -> int:
    settings = load_settings()
    status = 'ok' if settings.db_path.exists() else 'missing_db'
    print(f'STATUS={status}')
    print(f'DB_PATH={settings.db_path}')
    return 0 if status == 'ok' else 1


def _cmd_seed_sources() -> int:
    settings = load_settings()
    bootstrap_local_environment(settings)
    seeded_count = seed_default_sources(settings)
    print(f'SEEDED_SOURCE_COUNT={seeded_count}')
    return 0


def _cmd_list_sources() -> int:
    settings = load_settings()
    rows = list_sources(settings)
    print(f'SOURCE_COUNT={len(rows)}')
    for row in rows:
        print(
            '|'.join(
                [
                    row['source_id'],
                    row['source_tier'],
                    row['source_status'],
                    str(row['source_priority']),
                    row['source_kind'] or '',
                    row['source_name'],
                ]
            )
        )
    return 0


def _cmd_set_pipeline_state(
    pipeline_name: str,
    run_status: str,
    state_json: str,
) -> int:
    settings = load_settings()
    bootstrap_local_environment(settings)
    upsert_pipeline_state(
        settings,
        pipeline_name=pipeline_name,
        last_run_status=run_status,
        state_json=state_json,
        mark_success=run_status == 'success',
    )
    print(f'PIPELINE_NAME={pipeline_name}')
    print(f'LAST_RUN_STATUS={run_status}')
    print('PIPELINE_STATE_UPSERT=OK')
    return 0


def _cmd_show_pipeline_state(pipeline_name: str) -> int:
    settings = load_settings()
    row = get_pipeline_state(settings, pipeline_name)
    if row is None:
        print('STATUS=missing_pipeline_state')
        print(f'PIPELINE_NAME={pipeline_name}')
        return 1
    print('STATUS=ok')
    print(f"PIPELINE_NAME={row['pipeline_name']}")
    print(f"LAST_RUN_STATUS={row['last_run_status']}")
    print(f"STATE_JSON={row['state_json']}")
    return 0


def _cmd_list_adapters() -> int:
    settings = load_settings()
    rows = []
    for descriptor in list_adapter_descriptors():
        plan = build_adapter_plan(settings, descriptor.adapter_id)
        rows.append((descriptor, plan))
    print(f'ADAPTER_COUNT={len(rows)}')
    for descriptor, plan in rows:
        print(
            '|'.join(
                [
                    descriptor.adapter_id,
                    descriptor.source_tier,
                    descriptor.transport,
                    descriptor.extraction_mode,
                    'yes' if plan.registry_bound else 'no',
                    plan.source_status,
                    descriptor.source_name,
                ]
            )
        )
    return 0


def _cmd_describe_adapter(adapter_id: str) -> int:
    settings = load_settings()
    descriptor = get_adapter_descriptor(adapter_id)
    plan = build_adapter_plan(settings, adapter_id)
    if descriptor is None:
        raise ValueError(f'Unknown adapter_id={adapter_id}')
    print(f'ADAPTER_ID={descriptor.adapter_id}')
    print(f'SOURCE_NAME={descriptor.source_name}')
    print(f"REGISTRY_BOUND={'yes' if plan.registry_bound else 'no'}")
    print(f'TRANSPORT={descriptor.transport}')
    print(f'EXTRACTION_MODE={descriptor.extraction_mode}')
    print(f'RAW_LANDING_PREFIX={plan.raw_landing_prefix}')
    print(f'STAGE_DATASET={plan.stage_dataset}')
    print(f'SOURCE_STATUS={plan.source_status}')
    print(f'NOTES={descriptor.notes}')
    return 0


def _cmd_run_adapter(adapter_id: str, execute: bool) -> int:
    settings = load_settings()
    result = execute_fetch_contract(settings, adapter_id=adapter_id, execute=execute)
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'PIPELINE_NAME={result.pipeline_name}')
    print(f'RUN_MODE={result.run_mode}')
    print(f'RUN_STATUS={result.run_status}')
    print(f'INGEST_RUN_ID={result.ingest_run_id or ""}')
    print(f'LANDING_DIR={result.landing_dir}')
    print(f'MANIFEST_PATH={result.manifest_path or ""}')
    print(f'RECEIPT_PATH={result.receipt_path or ""}')
    print(f'LOAD_EVENT_ID={result.load_event_id or ""}')
    print(f'LANDED_FILE_COUNT={result.landed_file_count}')
    print(f'ASSET_COUNT={result.asset_count}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    return 0


def _cmd_fetch_remote(adapter_id: str, execute: bool, remote_url: str) -> int:
    settings = load_settings()
    result = execute_remote_fetch(
        settings,
        adapter_id=adapter_id,
        execute=execute,
        remote_url_override=remote_url or None,
    )
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'PIPELINE_NAME={result.pipeline_name}')
    print(f'RUN_MODE={result.run_mode}')
    print(f'RUN_STATUS={result.run_status}')
    print(f'INGEST_RUN_ID={result.ingest_run_id}')
    print(f'LANDING_DIR={result.landing_dir}')
    print(f'MANIFEST_PATH={result.manifest_path}')
    print(f'RECEIPT_PATH={result.receipt_path}')
    print(f'LOAD_EVENT_ID={result.load_event_id}')
    print(f'LANDED_FILE_COUNT={result.landed_file_count}')
    print(f'ASSET_COUNT={result.asset_count}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    print(f'SOURCE_URL={result.source_url}')
    print(f'DOWNLOADED_FILE_PATH={result.downloaded_file_path}')
    print(f'DOWNLOADED_BYTES={result.downloaded_bytes}')
    print(f'SHA256_HEX={result.sha256_hex}')
    return 0


def _cmd_stage_load(adapter_id: str, execute: bool, source_file_id: str) -> int:
    settings = load_settings()
    result = execute_stage_load(
        settings,
        adapter_id=adapter_id,
        execute=execute,
        source_file_id=source_file_id or None,
    )
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'PIPELINE_NAME={result.pipeline_name}')
    print(f'RUN_MODE={result.run_mode}')
    print(f'RUN_STATUS={result.run_status}')
    print(f'INGEST_RUN_ID={result.ingest_run_id}')
    print(f'SOURCE_FILE_ID={result.source_file_id}')
    print(f'SOURCE_FILE_PATH={result.source_file_path}')
    print(f'TARGET_SCHEMA={result.target_schema}')
    print(f'TARGET_OBJECT={result.target_object}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'ROW_COUNT={result.row_count}')
    print(f'LOAD_EVENT_ID={result.load_event_id}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    return 0


def _cmd_core_load(adapter_id: str, execute: bool) -> int:
    settings = load_settings()
    result = execute_core_load(settings, adapter_id=adapter_id, execute=execute)
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'PIPELINE_NAME={result.pipeline_name}')
    print(f'RUN_MODE={result.run_mode}')
    print(f'RUN_STATUS={result.run_status}')
    print(f'INGEST_RUN_ID={result.ingest_run_id}')
    print(f'SOURCE_SCHEMA={result.source_schema}')
    print(f'SOURCE_OBJECT={result.source_object}')
    print(f'SOURCE_TABLE={result.source_table}')
    print(f'TARGET_SCHEMA={result.target_schema}')
    print(f'TARGET_OBJECT={result.target_object}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'SOURCE_ROW_COUNT={result.source_row_count}')
    print(f'ROW_COUNT={result.row_count}')
    print(f'DISTINCT_KEY_COUNT={result.distinct_key_count}')
    print(f'INVALID_ROW_COUNT={result.invalid_row_count}')
    print(f'LOAD_EVENT_ID={result.load_event_id}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    return 0


def _cmd_browse_core(adapter_id: str, field_prefix: str, data_type: str, limit: int) -> int:
    settings = load_settings()
    result = browse_core_dictionary(
        settings,
        adapter_id=adapter_id,
        field_prefix=field_prefix,
        data_type_filter=data_type,
        limit=limit,
    )
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'SOURCE_SCHEMA={result.source_schema}')
    print(f'SOURCE_OBJECT={result.source_object}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'TOTAL_ROW_COUNT={result.total_row_count}')
    print(f'MATCH_ROW_COUNT={result.match_row_count}')
    print(f'RETURNED_ROW_COUNT={result.returned_row_count}')
    print(f'LIMIT={result.limit}')
    print(f'FIELD_PREFIX={result.field_prefix}')
    print(f'DATA_TYPE_FILTER={result.data_type_filter}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    for field, data_type_value, description in result.rows:
        print(f'ROW={field}|{data_type_value}|{description}')
    return 0


def _cmd_describe_core_field(adapter_id: str, field: str) -> int:
    settings = load_settings()
    result = lookup_core_dictionary_field(settings, adapter_id=adapter_id, field=field)
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'SOURCE_SCHEMA={result.source_schema}')
    print(f'SOURCE_OBJECT={result.source_object}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'REQUESTED_FIELD={result.requested_field}')
    print(f'NORMALIZED_FIELD={result.normalized_field}')
    print(f"FOUND={'yes' if result.found else 'no'}")
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    if result.found:
        print(f'FIELD={result.field}')
        print(f'DATA_TYPE={result.data_type}')
        print(f'DESCRIPTION={result.description}')
        return 0
    print(f'MISS_REASON={result.miss_reason}')
    print(f'SUGGESTION_COUNT={len(result.suggestions)}')
    for suggestion in result.suggestions:
        print(f'SUGGESTION={suggestion}')
    return 1


def _cmd_summarize_core(adapter_id: str) -> int:
    settings = load_settings()
    result = summarize_core_dictionary(settings, adapter_id=adapter_id)
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'SOURCE_SCHEMA={result.source_schema}')
    print(f'SOURCE_OBJECT={result.source_object}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'TOTAL_ROW_COUNT={result.total_row_count}')
    print(f'DISTINCT_DATA_TYPE_COUNT={result.distinct_data_type_count}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    for data_type, count in result.data_type_rows:
        print(f'DATA_TYPE_ROW={data_type}|{count}')
    return 0


def _cmd_list_source_files(adapter_id: str, limit: int) -> int:
    settings = load_settings()
    result = list_source_files(settings, adapter_id=adapter_id, limit=limit)
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'TOTAL_ROW_COUNT={result.total_row_count}')
    print(f'RETURNED_ROW_COUNT={result.returned_row_count}')
    print(f'LIMIT={result.limit}')
    print(f'STAGE_DATASET={result.stage_dataset}')
    print(f'SOURCE_STATUS={result.source_status}')
    for row in result.rows:
        source_file_id, created_at, local_path, file_size_bytes, sha256_hex, source_url = row
        print(
            'SOURCE_FILE_ROW=' + '|'.join(
                [
                    str(source_file_id),
                    str(created_at),
                    str(local_path),
                    str(file_size_bytes),
                    str(sha256_hex),
                    str(source_url),
                ]
            )
        )
    return 0


def _cmd_render_web_preview(adapter_id: str, output: str, limit: int, data_type: str) -> int:
    settings = load_settings()
    result = render_core_dictionary_preview(
        settings,
        adapter_id=adapter_id,
        output_path=output,
        limit=limit,
        data_type_filter=data_type,
    )
    print(f'ADAPTER_ID={result.adapter_id}')
    print(f'OUTPUT_PATH={result.output_path}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'TOTAL_ROW_COUNT={result.total_row_count}')
    print(f'MATCH_ROW_COUNT={result.match_row_count}')
    print(f'RETURNED_ROW_COUNT={result.returned_row_count}')
    print(f'DISTINCT_DATA_TYPE_COUNT={result.distinct_data_type_count}')
    print(f'LIMIT={result.limit}')
    print(f'DATA_TYPE_FILTER={result.data_type_filter}')
    return 0


def _cmd_serve_web_preview(
    adapter_id: str,
    host: str,
    port: int,
    limit: int,
    data_type: str,
) -> int:
    settings = load_settings()
    serve_web_preview(
        settings,
        adapter_id=adapter_id,
        host=host,
        port=port,
        limit=limit,
        data_type_filter=data_type,
    )
    return 0


def _cmd_list_ingest_runs(pipeline_name: str | None) -> int:
    settings = load_settings()
    rows = list_ingest_runs(settings, pipeline_name)
    print(f'RUN_COUNT={len(rows)}')
    for row in rows:
        print(
            '|'.join(
                [
                    row['ingest_run_id'],
                    row['pipeline_name'],
                    row['run_status'] or '',
                    row['run_mode'] or '',
                    row['trigger_kind'] or '',
                ]
            )
        )
    return 0


def _cmd_list_jobs() -> int:
    settings = load_settings()
    jobs = list_jobs(settings)
    print(f'JOB_COUNT={len(jobs)}')
    for job in jobs:
        print(
            '|'.join(
                [
                    job.job_key,
                    job.job_type,
                    job.target_ref or '',
                    'active' if job.is_active else 'inactive',
                    job.concurrency_key or '',
                    job.retry_policy_id or '',
                ]
            )
        )
    return 0


def _cmd_describe_job(job_key: str) -> int:
    settings = load_settings()
    result = describe_job(settings, job_key)
    if result is None:
        print(f'JOB_KEY={job_key}')
        print('STATUS=not_found')
        return 1
    job = result['job']
    retry_policy = result['retry_policy']
    schedules = result['schedules']
    recent_runs = result['recent_runs']
    print(f'JOB_KEY={job.job_key}')
    print(f'JOB_ID={job.job_id}')
    print(f'JOB_TYPE={job.job_type}')
    print(f'TARGET_REF={job.target_ref or ""}')
    print(f'DESCRIPTION={job.description or ""}')
    print(f'IS_ACTIVE={job.is_active}')
    print(f'CONCURRENCY_KEY={job.concurrency_key or ""}')
    print(f'PARAMS_JSON={job.params_json}')
    if retry_policy is not None:
        print(
            'RETRY_POLICY='
            f'{retry_policy.policy_key}|'
            f'{retry_policy.backoff_kind}|'
            f'max_attempts={retry_policy.max_attempts}|'
            f'base_seconds={retry_policy.base_seconds}'
        )
    else:
        print('RETRY_POLICY=')
    print(f'SCHEDULE_COUNT={len(schedules)}')
    for schedule in schedules:
        print(
            'SCHEDULE='
            f'{schedule.schedule_kind}|{schedule.schedule_expr or ""}|'
            f'tz={schedule.timezone or ""}|'
            f'active={schedule.is_active}'
        )
    print(f'RECENT_RUN_COUNT={len(recent_runs)}')
    for run in recent_runs:
        print(
            'RUN='
            f'{run.job_run_id}|{run.run_status}|'
            f'attempt={run.attempt_number}|'
            f'started_at={run.started_at or ""}'
        )
    return 0


def _cmd_register_job(
    job_key: str,
    job_type: str,
    target_ref: str,
    description: str,
    concurrency_key: str,
    params_json: str,
    retry_policy_key: str,
    inactive: bool,
) -> int:
    settings = load_settings()
    import json as _json
    params = _json.loads(params_json) if params_json else {}
    job = register_job(
        settings,
        job_key=job_key,
        job_type=job_type,  # type: ignore[arg-type]
        target_ref=target_ref or None,
        description=description or None,
        is_active=not inactive,
        concurrency_key=concurrency_key or None,
        params=params,
        retry_policy_key=retry_policy_key or None,
    )
    print(f'JOB_KEY={job.job_key}')
    print(f'JOB_ID={job.job_id}')
    print('STATUS=registered')
    return 0


def _cmd_register_retry_policy(
    policy_key: str,
    max_attempts: int,
    backoff_kind: str,
    base_seconds: int,
    max_seconds: int,
    jitter_ratio: float,
    notes: str,
) -> int:
    settings = load_settings()
    policy = register_retry_policy(
        settings,
        policy_key=policy_key,
        max_attempts=max_attempts,
        backoff_kind=backoff_kind,  # type: ignore[arg-type]
        base_seconds=base_seconds,
        max_seconds=max_seconds if max_seconds > 0 else None,
        jitter_ratio=jitter_ratio if jitter_ratio > 0 else None,
        notes=notes or None,
    )
    print(f'POLICY_KEY={policy.policy_key}')
    print(f'POLICY_ID={policy.retry_policy_id}')
    print('STATUS=registered')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='new-nfl',
        description='NEW NFL local tooling',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser(
        'bootstrap',
        help='Create local directories and baseline DuckDB metadata surface',
    )
    sub.add_parser('health', help='Check whether the baseline database exists')
    sub.add_parser('seed-sources', help='Seed the default source registry entries')
    sub.add_parser('list-sources', help='List source registry entries')
    sub.add_parser('list-adapters', help='List adapter descriptors')

    describe_adapter = sub.add_parser('describe-adapter', help='Describe one adapter')
    describe_adapter.add_argument('--adapter-id', required=True)

    run_adapter = sub.add_parser(
        'run-adapter',
        help='Execute the fetch contract for one adapter',
    )
    run_adapter.add_argument('--adapter-id', required=True)
    run_adapter.add_argument('--execute', action='store_true')

    fetch_remote = sub.add_parser(
        'fetch-remote',
        help='Perform a first true remote fetch',
    )
    fetch_remote.add_argument('--adapter-id', required=True)
    fetch_remote.add_argument('--execute', action='store_true')
    fetch_remote.add_argument('--remote-url', default='')

    stage_load = sub.add_parser(
        'stage-load',
        help='Load one remote CSV into the first staging table',
    )
    stage_load.add_argument('--adapter-id', required=True)
    stage_load.add_argument('--execute', action='store_true')
    stage_load.add_argument('--source-file-id', default='')

    core_load = sub.add_parser(
        'core-load',
        help='Load the first canonical reference slice from stage to core',
    )
    core_load.add_argument('--adapter-id', required=True)
    core_load.add_argument('--execute', action='store_true')

    browse_core = sub.add_parser(
        'browse-core',
        help='Browse rows from the first core dictionary slice',
    )
    browse_core.add_argument('--adapter-id', required=True)
    browse_core.add_argument('--field-prefix', default='')
    browse_core.add_argument('--data-type', default='')
    browse_core.add_argument('--limit', type=int, default=20)

    describe_core_field = sub.add_parser(
        'describe-core-field',
        help='Look up one exact field in the first core dictionary slice',
    )
    describe_core_field.add_argument('--adapter-id', required=True)
    describe_core_field.add_argument('--field', required=True)

    summarize_core = sub.add_parser(
        'summarize-core',
        help='Summarize the first core dictionary slice by data type',
    )
    summarize_core.add_argument('--adapter-id', required=True)

    list_source_files_parser = sub.add_parser(
        'list-source-files',
        help='List registered source files for one adapter',
    )
    list_source_files_parser.add_argument('--adapter-id', required=True)
    list_source_files_parser.add_argument('--limit', type=int, default=20)

    render_web_preview = sub.add_parser(
        'render-web-preview',
        help='Render a local HTML preview for the first core dictionary slice',
    )
    render_web_preview.add_argument('--adapter-id', required=True)
    render_web_preview.add_argument('--output', required=True)
    render_web_preview.add_argument('--limit', type=int, default=20)
    render_web_preview.add_argument('--data-type', default='')

    serve_web_preview_parser = sub.add_parser(
        'serve-web-preview',
        help='Serve the local core dictionary preview over HTTP',
    )
    serve_web_preview_parser.add_argument('--adapter-id', required=True)
    serve_web_preview_parser.add_argument('--host', default='127.0.0.1')
    serve_web_preview_parser.add_argument('--port', type=int, default=8787)
    serve_web_preview_parser.add_argument('--limit', type=int, default=20)
    serve_web_preview_parser.add_argument('--data-type', default='')

    list_runs = sub.add_parser('list-ingest-runs', help='List ingest runs')
    list_runs.add_argument('--pipeline-name', default=None)

    set_state = sub.add_parser(
        'set-pipeline-state',
        help='Upsert one pipeline state record',
    )
    set_state.add_argument('--pipeline-name', required=True)
    set_state.add_argument('--run-status', required=True)
    set_state.add_argument('--state-json', default='{}')

    show_state = sub.add_parser(
        'show-pipeline-state',
        help='Show one pipeline state record',
    )
    show_state.add_argument('--pipeline-name', required=True)

    sub.add_parser('list-jobs', help='List registered job definitions')

    describe_job_parser = sub.add_parser(
        'describe-job',
        help='Describe one job definition with schedules and recent runs',
    )
    describe_job_parser.add_argument('--job-key', required=True)

    register_job_parser = sub.add_parser(
        'register-job',
        help='Register or update a job definition',
    )
    register_job_parser.add_argument('--job-key', required=True)
    register_job_parser.add_argument('--job-type', required=True)
    register_job_parser.add_argument('--target-ref', default='')
    register_job_parser.add_argument('--description', default='')
    register_job_parser.add_argument('--concurrency-key', default='')
    register_job_parser.add_argument('--params-json', default='{}')
    register_job_parser.add_argument('--retry-policy-key', default='')
    register_job_parser.add_argument('--inactive', action='store_true')

    register_policy_parser = sub.add_parser(
        'register-retry-policy',
        help='Register or update a retry policy',
    )
    register_policy_parser.add_argument('--policy-key', required=True)
    register_policy_parser.add_argument('--max-attempts', type=int, required=True)
    register_policy_parser.add_argument('--backoff-kind', required=True)
    register_policy_parser.add_argument('--base-seconds', type=int, required=True)
    register_policy_parser.add_argument('--max-seconds', type=int, default=0)
    register_policy_parser.add_argument('--jitter-ratio', type=float, default=0.0)
    register_policy_parser.add_argument('--notes', default='')

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == 'bootstrap':
        return _cmd_bootstrap()
    if args.command == 'health':
        return _cmd_health()
    if args.command == 'seed-sources':
        return _cmd_seed_sources()
    if args.command == 'list-sources':
        return _cmd_list_sources()
    if args.command == 'list-adapters':
        return _cmd_list_adapters()
    if args.command == 'describe-adapter':
        return _cmd_describe_adapter(args.adapter_id)
    if args.command == 'run-adapter':
        return _cmd_run_adapter(args.adapter_id, args.execute)
    if args.command == 'fetch-remote':
        return _cmd_fetch_remote(args.adapter_id, args.execute, args.remote_url)
    if args.command == 'stage-load':
        return _cmd_stage_load(args.adapter_id, args.execute, args.source_file_id)
    if args.command == 'core-load':
        return _cmd_core_load(args.adapter_id, args.execute)
    if args.command == 'browse-core':
        return _cmd_browse_core(args.adapter_id, args.field_prefix, args.data_type, args.limit)
    if args.command == 'describe-core-field':
        return _cmd_describe_core_field(args.adapter_id, args.field)
    if args.command == 'summarize-core':
        return _cmd_summarize_core(args.adapter_id)
    if args.command == 'list-source-files':
        return _cmd_list_source_files(args.adapter_id, args.limit)
    if args.command == 'render-web-preview':
        return _cmd_render_web_preview(args.adapter_id, args.output, args.limit, args.data_type)
    if args.command == 'serve-web-preview':
        return _cmd_serve_web_preview(
            args.adapter_id,
            args.host,
            args.port,
            args.limit,
            args.data_type,
        )
    if args.command == 'list-ingest-runs':
        return _cmd_list_ingest_runs(args.pipeline_name)
    if args.command == 'set-pipeline-state':
        return _cmd_set_pipeline_state(
            args.pipeline_name,
            args.run_status,
            args.state_json,
        )
    if args.command == 'show-pipeline-state':
        return _cmd_show_pipeline_state(args.pipeline_name)
    if args.command == 'list-jobs':
        return _cmd_list_jobs()
    if args.command == 'describe-job':
        return _cmd_describe_job(args.job_key)
    if args.command == 'register-job':
        return _cmd_register_job(
            args.job_key,
            args.job_type,
            args.target_ref,
            args.description,
            args.concurrency_key,
            args.params_json,
            args.retry_policy_key,
            args.inactive,
        )
    if args.command == 'register-retry-policy':
        return _cmd_register_retry_policy(
            args.policy_key,
            args.max_attempts,
            args.backoff_kind,
            args.base_seconds,
            args.max_seconds,
            args.jitter_ratio,
            args.notes,
        )

    parser.error('Unknown command')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
