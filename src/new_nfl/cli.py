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
from new_nfl.metadata import (
    get_pipeline_state,
    list_ingest_runs,
    list_sources,
    seed_default_sources,
    upsert_pipeline_state,
)
from new_nfl.settings import load_settings


def _cmd_bootstrap() -> int:
    settings = load_settings()
    db_path = bootstrap_local_environment(settings)
    print(f"ENV={settings.env}")
    print(f"REPO_ROOT={settings.repo_root}")
    print(f"DATA_ROOT={settings.data_root}")
    print(f"DB_PATH={db_path}")
    print("BOOTSTRAP=OK")
    return 0


def _cmd_health() -> int:
    settings = load_settings()
    status = "ok" if settings.db_path.exists() else "missing_db"
    print(f"STATUS={status}")
    print(f"DB_PATH={settings.db_path}")
    return 0 if status == "ok" else 1


def _cmd_seed_sources() -> int:
    settings = load_settings()
    bootstrap_local_environment(settings)
    seeded_count = seed_default_sources(settings)
    print(f"SEEDED_SOURCE_COUNT={seeded_count}")
    return 0


def _cmd_list_sources() -> int:
    settings = load_settings()
    rows = list_sources(settings)
    print(f"SOURCE_COUNT={len(rows)}")
    for row in rows:
        print(
            "|".join(
                [
                    row["source_id"],
                    row["source_tier"],
                    row["source_status"],
                    str(row["source_priority"]),
                    row["source_kind"] or "",
                    row["source_name"],
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
        mark_success=run_status == "success",
    )
    print(f"PIPELINE_NAME={pipeline_name}")
    print(f"LAST_RUN_STATUS={run_status}")
    print("PIPELINE_STATE_UPSERT=OK")
    return 0


def _cmd_show_pipeline_state(pipeline_name: str) -> int:
    settings = load_settings()
    row = get_pipeline_state(settings, pipeline_name)
    if row is None:
        print("STATUS=missing_pipeline_state")
        print(f"PIPELINE_NAME={pipeline_name}")
        return 1
    print("STATUS=ok")
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
    print(f"ADAPTER_COUNT={len(rows)}")
    for descriptor, plan in rows:
        print(
            "|".join(
                [
                    descriptor.adapter_id,
                    descriptor.source_tier,
                    descriptor.transport,
                    descriptor.extraction_mode,
                    "yes" if plan.registry_bound else "no",
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
    print(f"ADAPTER_ID={descriptor.adapter_id}")
    print(f"SOURCE_NAME={descriptor.source_name}")
    print(f"REGISTRY_BOUND={'yes' if plan.registry_bound else 'no'}")
    print(f"TRANSPORT={descriptor.transport}")
    print(f"EXTRACTION_MODE={descriptor.extraction_mode}")
    print(f"RAW_LANDING_PREFIX={plan.raw_landing_prefix}")
    print(f"STAGE_DATASET={descriptor.stage_dataset}")
    print(f"SOURCE_STATUS={plan.source_status}")
    print(f"NOTES={descriptor.notes}")
    return 0


def _cmd_run_adapter(adapter_id: str, execute: bool) -> int:
    settings = load_settings()
    result = execute_fetch_contract(settings, adapter_id=adapter_id, execute=execute)
    print(f"ADAPTER_ID={result.adapter_id}")
    print(f"PIPELINE_NAME={result.pipeline_name}")
    print(f"RUN_MODE={result.run_mode}")
    print(f"RUN_STATUS={result.run_status}")
    print(f"INGEST_RUN_ID={result.ingest_run_id or ''}")
    print(f"LANDING_DIR={result.landing_dir}")
    print(f"MANIFEST_PATH={result.manifest_path or ''}")
    print(f"RECEIPT_PATH={result.receipt_path or ''}")
    print(f"LOAD_EVENT_ID={result.load_event_id or ''}")
    print(f"LANDED_FILE_COUNT={result.landed_file_count}")
    print(f"ASSET_COUNT={result.asset_count}")
    print(f"STAGE_DATASET={result.stage_dataset}")
    print(f"SOURCE_STATUS={result.source_status}")
    return 0


def _cmd_fetch_remote(adapter_id: str, execute: bool, remote_url: str) -> int:
    settings = load_settings()
    result = execute_remote_fetch(
        settings,
        adapter_id=adapter_id,
        execute=execute,
        remote_url_override=remote_url or None,
    )
    print(f"ADAPTER_ID={result.adapter_id}")
    print(f"PIPELINE_NAME={result.pipeline_name}")
    print(f"RUN_MODE={result.run_mode}")
    print(f"RUN_STATUS={result.run_status}")
    print(f"INGEST_RUN_ID={result.ingest_run_id}")
    print(f"LANDING_DIR={result.landing_dir}")
    print(f"MANIFEST_PATH={result.manifest_path}")
    print(f"RECEIPT_PATH={result.receipt_path}")
    print(f"LOAD_EVENT_ID={result.load_event_id}")
    print(f"LANDED_FILE_COUNT={result.landed_file_count}")
    print(f"ASSET_COUNT={result.asset_count}")
    print(f"STAGE_DATASET={result.stage_dataset}")
    print(f"SOURCE_STATUS={result.source_status}")
    print(f"SOURCE_URL={result.source_url}")
    print(f"DOWNLOADED_FILE_PATH={result.downloaded_file_path}")
    print(f"DOWNLOADED_BYTES={result.downloaded_bytes}")
    print(f"SHA256_HEX={result.sha256_hex}")
    return 0


def _cmd_list_ingest_runs(pipeline_name: str | None) -> int:
    settings = load_settings()
    rows = list_ingest_runs(settings, pipeline_name)
    print(f"RUN_COUNT={len(rows)}")
    for row in rows:
        print(
            "|".join(
                [
                    row["ingest_run_id"],
                    row["pipeline_name"],
                    row["run_status"] or "",
                    row["run_mode"] or "",
                    row["trigger_kind"] or "",
                ]
            )
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="new-nfl",
        description="NEW NFL local tooling",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "bootstrap",
        help="Create local directories and baseline DuckDB metadata surface",
    )
    sub.add_parser("health", help="Check whether the baseline database exists")
    sub.add_parser("seed-sources", help="Seed the default source registry entries")
    sub.add_parser("list-sources", help="List source registry entries")
    sub.add_parser("list-adapters", help="List adapter descriptors")

    describe_adapter = sub.add_parser("describe-adapter", help="Describe one adapter")
    describe_adapter.add_argument("--adapter-id", required=True)

    run_adapter = sub.add_parser(
        "run-adapter",
        help="Execute the fetch contract for one adapter",
    )
    run_adapter.add_argument("--adapter-id", required=True)
    run_adapter.add_argument("--execute", action="store_true")

    fetch_remote = sub.add_parser(
        "fetch-remote",
        help="Perform a first true remote fetch",
    )
    fetch_remote.add_argument("--adapter-id", required=True)
    fetch_remote.add_argument("--execute", action="store_true")
    fetch_remote.add_argument("--remote-url", default="")

    list_runs = sub.add_parser("list-ingest-runs", help="List ingest runs")
    list_runs.add_argument("--pipeline-name", default=None)

    set_state = sub.add_parser(
        "set-pipeline-state",
        help="Upsert one pipeline state record",
    )
    set_state.add_argument("--pipeline-name", required=True)
    set_state.add_argument("--run-status", required=True)
    set_state.add_argument("--state-json", default="{}")

    show_state = sub.add_parser(
        "show-pipeline-state",
        help="Show one pipeline state record",
    )
    show_state.add_argument("--pipeline-name", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "bootstrap":
        return _cmd_bootstrap()
    if args.command == "health":
        return _cmd_health()
    if args.command == "seed-sources":
        return _cmd_seed_sources()
    if args.command == "list-sources":
        return _cmd_list_sources()
    if args.command == "list-adapters":
        return _cmd_list_adapters()
    if args.command == "describe-adapter":
        return _cmd_describe_adapter(args.adapter_id)
    if args.command == "run-adapter":
        return _cmd_run_adapter(args.adapter_id, args.execute)
    if args.command == "fetch-remote":
        return _cmd_fetch_remote(args.adapter_id, args.execute, args.remote_url)
    if args.command == "list-ingest-runs":
        return _cmd_list_ingest_runs(args.pipeline_name)
    if args.command == "set-pipeline-state":
        return _cmd_set_pipeline_state(
            args.pipeline_name,
            args.run_status,
            args.state_json,
        )
    if args.command == "show-pipeline-state":
        return _cmd_show_pipeline_state(args.pipeline_name)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
