from __future__ import annotations

import json
import uuid
from hashlib import sha256
from pathlib import Path
from typing import Any

import duckdb

from new_nfl.settings import Settings

SCHEMA_NAMES = ("meta", "raw", "stg", "core", "mart", "feat", "sim", "scratch")

TABLE_SPECS: dict[str, dict[str, Any]] = {
    "source_registry": {
        "primary_key": "source_id",
        "columns": {
            "source_id": "VARCHAR",
            "source_key": "VARCHAR",
            "source_name": "VARCHAR NOT NULL",
            "source_tier": "VARCHAR NOT NULL",
            "source_status": "VARCHAR NOT NULL",
            "source_priority": "INTEGER",
            "source_kind": "VARCHAR",
            "source_family": "VARCHAR",
            "access_mode": "VARCHAR",
            "default_frequency": "VARCHAR",
            "landing_zone": "VARCHAR",
            "owner_note": "VARCHAR",
            "transport": "VARCHAR",
            "extraction_mode": "VARCHAR",
            "default_remote_url": "VARCHAR",
            "notes": "VARCHAR",
            "is_active": "BOOLEAN",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ingest_runs": {
        "primary_key": "ingest_run_id",
        "columns": {
            "ingest_run_id": "VARCHAR",
            "pipeline_name": "VARCHAR NOT NULL",
            "adapter_id": "VARCHAR",
            "run_status": "VARCHAR NOT NULL",
            "triggered_by": "VARCHAR",
            "trigger_kind": "VARCHAR",
            "run_mode": "VARCHAR",
            "landing_dir": "VARCHAR",
            "manifest_path": "VARCHAR",
            "receipt_path": "VARCHAR",
            "asset_count": "INTEGER",
            "landed_file_count": "INTEGER",
            "message": "VARCHAR",
            "detail_json": "VARCHAR",
            "started_at": "TIMESTAMP DEFAULT current_timestamp",
            "finished_at": "TIMESTAMP",
        },
    },
    "load_events": {
        "primary_key": "load_event_id",
        "columns": {
            "load_event_id": "VARCHAR",
            "ingest_run_id": "VARCHAR",
            "source_id": "VARCHAR",
            "source_key": "VARCHAR",
            "pipeline_name": "VARCHAR",
            "event_kind": "VARCHAR",
            "target_schema": "VARCHAR",
            "target_object": "VARCHAR",
            "object_path": "VARCHAR",
            "row_count": "BIGINT",
            "event_status": "VARCHAR",
            "payload_json": "VARCHAR",
            "detail_json": "VARCHAR",
            "recorded_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "dq_events": {
        "primary_key": "dq_event_id",
        "columns": {
            "dq_event_id": "VARCHAR",
            "ingest_run_id": "VARCHAR",
            "source_id": "VARCHAR",
            "severity": "VARCHAR NOT NULL",
            "dq_rule_code": "VARCHAR NOT NULL",
            "target_schema": "VARCHAR",
            "target_object": "VARCHAR",
            "affected_row_count": "BIGINT",
            "detail_json": "VARCHAR",
            "recorded_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "pipeline_state": {
        "primary_key": "pipeline_name",
        "columns": {
            "pipeline_name": "VARCHAR",
            "pipeline_key": "VARCHAR",
            "last_run_status": "VARCHAR",
            "last_success_at": "TIMESTAMP",
            "last_attempt_at": "TIMESTAMP",
            "state_json": "VARCHAR",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "source_files": {
        "primary_key": "source_file_id",
        "columns": {
            "source_file_id": "VARCHAR",
            "ingest_run_id": "VARCHAR",
            "adapter_id": "VARCHAR",
            "source_url": "VARCHAR",
            "local_path": "VARCHAR",
            "file_size_bytes": "BIGINT",
            "sha256_hex": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "retry_policy": {
        "primary_key": "retry_policy_id",
        "columns": {
            "retry_policy_id": "VARCHAR",
            "policy_key": "VARCHAR NOT NULL",
            "max_attempts": "INTEGER NOT NULL",
            "backoff_kind": "VARCHAR NOT NULL",
            "base_seconds": "INTEGER NOT NULL",
            "max_seconds": "INTEGER",
            "jitter_ratio": "DOUBLE",
            "notes": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "job_definition": {
        "primary_key": "job_id",
        "columns": {
            "job_id": "VARCHAR",
            "job_key": "VARCHAR NOT NULL",
            "job_type": "VARCHAR NOT NULL",
            "target_ref": "VARCHAR",
            "description": "VARCHAR",
            "is_active": "BOOLEAN",
            "concurrency_key": "VARCHAR",
            "params_json": "VARCHAR",
            "retry_policy_id": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "job_schedule": {
        "primary_key": "schedule_id",
        "columns": {
            "schedule_id": "VARCHAR",
            "job_id": "VARCHAR NOT NULL",
            "schedule_kind": "VARCHAR NOT NULL",
            "schedule_expr": "VARCHAR",
            "timezone": "VARCHAR",
            "is_active": "BOOLEAN",
            "next_fire_at": "TIMESTAMP",
            "last_fired_at": "TIMESTAMP",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "job_queue": {
        "primary_key": "queue_item_id",
        "columns": {
            "queue_item_id": "VARCHAR",
            "job_id": "VARCHAR NOT NULL",
            "idempotency_key": "VARCHAR",
            "priority": "INTEGER",
            "trigger_kind": "VARCHAR",
            "claim_status": "VARCHAR NOT NULL",
            "claimed_by": "VARCHAR",
            "claimed_at": "TIMESTAMP",
            "attempt_count": "INTEGER",
            "params_json": "VARCHAR",
            "scheduled_for": "TIMESTAMP",
            "enqueued_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "job_run": {
        "primary_key": "job_run_id",
        "columns": {
            "job_run_id": "VARCHAR",
            "job_id": "VARCHAR NOT NULL",
            "queue_item_id": "VARCHAR",
            "run_status": "VARCHAR NOT NULL",
            "attempt_number": "INTEGER",
            "worker_id": "VARCHAR",
            "message": "VARCHAR",
            "detail_json": "VARCHAR",
            "started_at": "TIMESTAMP DEFAULT current_timestamp",
            "finished_at": "TIMESTAMP",
        },
    },
    "run_event": {
        "primary_key": "run_event_id",
        "columns": {
            "run_event_id": "VARCHAR",
            "job_run_id": "VARCHAR NOT NULL",
            "event_kind": "VARCHAR NOT NULL",
            "severity": "VARCHAR",
            "message": "VARCHAR",
            "detail_json": "VARCHAR",
            "recorded_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "run_artifact": {
        "primary_key": "run_artifact_id",
        "columns": {
            "run_artifact_id": "VARCHAR",
            "job_run_id": "VARCHAR NOT NULL",
            "artifact_kind": "VARCHAR NOT NULL",
            "ref_id": "VARCHAR",
            "ref_path": "VARCHAR",
            "detail_json": "VARCHAR",
            "recorded_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "quarantine_case": {
        "primary_key": "quarantine_case_id",
        "columns": {
            "quarantine_case_id": "VARCHAR",
            "scope_type": "VARCHAR NOT NULL",
            "scope_ref": "VARCHAR NOT NULL",
            "reason_code": "VARCHAR NOT NULL",
            "severity": "VARCHAR NOT NULL",
            "evidence_refs_json": "VARCHAR",
            "status": "VARCHAR NOT NULL",
            "owner": "VARCHAR",
            "notes": "VARCHAR",
            "first_seen_at": "TIMESTAMP DEFAULT current_timestamp",
            "last_seen_at": "TIMESTAMP DEFAULT current_timestamp",
            "resolved_at": "TIMESTAMP",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "recovery_action": {
        "primary_key": "recovery_action_id",
        "columns": {
            "recovery_action_id": "VARCHAR",
            "quarantine_case_id": "VARCHAR NOT NULL",
            "action_kind": "VARCHAR NOT NULL",
            "triggered_by": "VARCHAR",
            "resulting_run_id": "VARCHAR",
            "note": "VARCHAR",
            "detail_json": "VARCHAR",
            "triggered_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ontology_version": {
        "primary_key": "ontology_version_id",
        "columns": {
            "ontology_version_id": "VARCHAR",
            "version_label": "VARCHAR NOT NULL",
            "source_dir": "VARCHAR NOT NULL",
            "content_sha256": "VARCHAR NOT NULL",
            "file_count": "INTEGER NOT NULL",
            "term_count": "INTEGER NOT NULL",
            "alias_count": "INTEGER NOT NULL",
            "value_set_count": "INTEGER NOT NULL",
            "value_set_member_count": "INTEGER NOT NULL",
            "is_active": "BOOLEAN DEFAULT FALSE",
            "loaded_at": "TIMESTAMP DEFAULT current_timestamp",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ontology_term": {
        "primary_key": "ontology_term_id",
        "columns": {
            "ontology_term_id": "VARCHAR",
            "ontology_version_id": "VARCHAR NOT NULL",
            "term_key": "VARCHAR NOT NULL",
            "label": "VARCHAR",
            "description": "VARCHAR",
            "source_path": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ontology_alias": {
        "primary_key": "ontology_alias_id",
        "columns": {
            "ontology_alias_id": "VARCHAR",
            "ontology_term_id": "VARCHAR NOT NULL",
            "alias": "VARCHAR NOT NULL",
            "alias_lower": "VARCHAR NOT NULL",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ontology_value_set": {
        "primary_key": "ontology_value_set_id",
        "columns": {
            "ontology_value_set_id": "VARCHAR",
            "ontology_term_id": "VARCHAR NOT NULL",
            "value_set_key": "VARCHAR NOT NULL",
            "label": "VARCHAR",
            "description": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ontology_value_set_member": {
        "primary_key": "ontology_value_set_member_id",
        "columns": {
            "ontology_value_set_member_id": "VARCHAR",
            "ontology_value_set_id": "VARCHAR NOT NULL",
            "value": "VARCHAR NOT NULL",
            "value_lower": "VARCHAR NOT NULL",
            "label": "VARCHAR",
            "ordinal": "INTEGER",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ontology_mapping": {
        "primary_key": "ontology_mapping_id",
        "columns": {
            "ontology_mapping_id": "VARCHAR",
            "ontology_version_id": "VARCHAR NOT NULL",
            "from_term_key": "VARCHAR NOT NULL",
            "from_value": "VARCHAR NOT NULL",
            "to_term_key": "VARCHAR NOT NULL",
            "to_value": "VARCHAR NOT NULL",
            "mapping_kind": "VARCHAR NOT NULL",
            "description": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "dedupe_run": {
        "primary_key": "dedupe_run_id",
        "columns": {
            "dedupe_run_id": "VARCHAR",
            "domain": "VARCHAR NOT NULL",
            "source_ref": "VARCHAR",
            "scorer_kind": "VARCHAR NOT NULL",
            "lower_threshold": "DOUBLE NOT NULL",
            "upper_threshold": "DOUBLE NOT NULL",
            "input_record_count": "INTEGER NOT NULL",
            "candidate_pair_count": "INTEGER NOT NULL",
            "auto_merge_pair_count": "INTEGER NOT NULL",
            "review_pair_count": "INTEGER NOT NULL",
            "cluster_count": "INTEGER NOT NULL",
            "run_status": "VARCHAR NOT NULL",
            "message": "VARCHAR",
            "started_at": "TIMESTAMP DEFAULT current_timestamp",
            "ended_at": "TIMESTAMP",
        },
    },
    "review_item": {
        "primary_key": "review_item_id",
        "columns": {
            "review_item_id": "VARCHAR",
            "dedupe_run_id": "VARCHAR NOT NULL",
            "domain": "VARCHAR NOT NULL",
            "left_record_id": "VARCHAR NOT NULL",
            "right_record_id": "VARCHAR NOT NULL",
            "score": "DOUBLE NOT NULL",
            "block_key": "VARCHAR",
            "left_payload_json": "VARCHAR",
            "right_payload_json": "VARCHAR",
            "status": "VARCHAR NOT NULL DEFAULT 'open'",
            "resolution": "VARCHAR",
            "note": "VARCHAR",
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "resolved_at": "TIMESTAMP",
        },
    },
}

DEFAULT_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "source_id": "nflverse_bulk",
        "source_key": "nflverse_bulk",
        "source_name": "nflverse bulk datasets",
        "source_tier": "A",
        "source_status": "candidate",
        "source_priority": 10,
        "source_kind": "dataset",
        "source_family": "bulk",
        "access_mode": "http",
        "default_frequency": "daily",
        "landing_zone": "raw",
        "owner_note": "Primary bulk candidate for schedules, rosters, and historical stats.",
        "transport": "file",
        "extraction_mode": "bulk_snapshot",
        "default_remote_url": (
            "https://raw.githubusercontent.com/nflverse/nflreadr/"
            "1f23027a27ec565f1272345a80a208b8f529f0fc/data-raw/dictionary_schedules.csv"
        ),
        "notes": "Primary bulk adapter skeleton for historical and weekly datasets.",
        "is_active": True,
    },
    {
        "source_id": "official_context_web",
        "source_key": "official_context_web",
        "source_name": "official context web source",
        "source_tier": "B",
        "source_status": "candidate",
        "source_priority": 20,
        "source_kind": "web",
        "source_family": "context",
        "access_mode": "html",
        "default_frequency": "daily",
        "landing_zone": "raw",
        "owner_note": (
            "Secondary context source for official schedule and status confirmation."
        ),
        "transport": "http",
        "extraction_mode": "context_enrichment",
        "default_remote_url": "",
        "notes": "Secondary context enrichment source.",
        "is_active": True,
    },
    {
        "source_id": "public_stats_api",
        "source_key": "public_stats_api",
        "source_name": "public stats api candidate",
        "source_tier": "B",
        "source_status": "candidate",
        "source_priority": 30,
        "source_kind": "api",
        "source_family": "stats",
        "access_mode": "json",
        "default_frequency": "daily",
        "landing_zone": "raw",
        "owner_note": (
            "Secondary structured source for near-current stats and cross-checks."
        ),
        "transport": "http",
        "extraction_mode": "incremental_api",
        "default_remote_url": "",
        "notes": "Secondary API adapter skeleton for structured near-real-time stats feeds.",
        "is_active": True,
    },
    {
        "source_id": "reference_html_fallback",
        "source_key": "reference_html_fallback",
        "source_name": "reference html fallback",
        "source_tier": "C",
        "source_status": "candidate",
        "source_priority": 90,
        "source_kind": "web",
        "source_family": "fallback",
        "access_mode": "html",
        "default_frequency": "on-demand",
        "landing_zone": "raw",
        "owner_note": (
            "Fallback source class when structured sources are incomplete or delayed."
        ),
        "transport": "http",
        "extraction_mode": "html_fallback",
        "default_remote_url": "",
        "notes": "Reference HTML fallback adapter skeleton.",
        "is_active": True,
    },
)


def _connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.db_path))


def _column_names(con: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'meta' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()
    return {row[0] for row in rows}


def _create_table_statement(
    table_name: str,
    primary_key: str,
    columns: dict[str, str],
) -> str:
    column_defs = []
    for column_name, column_sql in columns.items():
        suffix = " PRIMARY KEY" if column_name == primary_key else ""
        column_defs.append(f"{column_name} {column_sql}{suffix}")
    joined = ",\n        ".join(column_defs)
    return f"""
    CREATE TABLE IF NOT EXISTS meta.{table_name} (
        {joined}
    )
    """


def _add_missing_columns(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    columns: dict[str, str],
) -> set[str]:
    existing = _column_names(con, table_name)
    for column_name, column_sql in columns.items():
        if column_name not in existing:
            alter_type = column_sql.split()[0]
            con.execute(
                f"ALTER TABLE meta.{table_name} ADD COLUMN {column_name} {alter_type}"
            )
    return _column_names(con, table_name)


def _coalesce_identifier(column_names: set[str], modern: str, legacy: str) -> str:
    if modern in column_names and legacy in column_names:
        return f"COALESCE({modern}, {legacy})"
    if modern in column_names:
        return modern
    return legacy


def _source_transport_expr(columns: set[str]) -> str:
    if "transport" in columns and "access_mode" in columns:
        return (
            "COALESCE(transport, "
            "CASE access_mode "
            "WHEN 'html' THEN 'http' "
            "WHEN 'json' THEN 'http' "
            "ELSE access_mode END)"
        )
    if "transport" in columns:
        return "transport"
    if "access_mode" in columns:
        return (
            "CASE access_mode "
            "WHEN 'html' THEN 'http' "
            "WHEN 'json' THEN 'http' "
            "ELSE access_mode END"
        )
    return "NULL"


def _source_extraction_expr(columns: set[str]) -> str:
    if "extraction_mode" in columns and "source_family" in columns:
        return (
            "COALESCE(extraction_mode, "
            "CASE source_family "
            "WHEN 'bulk' THEN 'bulk_snapshot' "
            "WHEN 'stats' THEN 'incremental_api' "
            "WHEN 'context' THEN 'context_enrichment' "
            "WHEN 'fallback' THEN 'html_fallback' "
            "ELSE NULL END)"
        )
    if "extraction_mode" in columns:
        return "extraction_mode"
    if "source_family" in columns:
        return (
            "CASE source_family "
            "WHEN 'bulk' THEN 'bulk_snapshot' "
            "WHEN 'stats' THEN 'incremental_api' "
            "WHEN 'context' THEN 'context_enrichment' "
            "WHEN 'fallback' THEN 'html_fallback' "
            "ELSE NULL END"
        )
    return "NULL"


def _source_status_expr(columns: set[str]) -> str:
    if "source_status" in columns and "is_active" in columns:
        return (
            "COALESCE(source_status, "
            "CASE WHEN is_active THEN 'candidate' ELSE 'inactive' END)"
        )
    if "source_status" in columns:
        return "source_status"
    if "is_active" in columns:
        return "CASE WHEN is_active THEN 'candidate' ELSE 'inactive' END"
    return "'candidate'"


def _backfill_source_registry(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
    if "source_id" in column_names and "source_key" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET source_id = source_key
            WHERE source_id IS NULL AND source_key IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.source_registry
            SET source_key = source_id
            WHERE source_key IS NULL AND source_id IS NOT NULL
            """
        )
    if "source_status" in column_names:
        if "is_active" in column_names:
            con.execute(
                """
                UPDATE meta.source_registry
                SET source_status = CASE WHEN is_active THEN 'candidate' ELSE 'inactive' END
                WHERE source_status IS NULL
                """
            )
        else:
            con.execute(
                """
                UPDATE meta.source_registry
                SET source_status = 'candidate'
                WHERE source_status IS NULL
                """
            )
    if "transport" in column_names and "access_mode" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET transport = CASE access_mode
                WHEN 'html' THEN 'http'
                WHEN 'json' THEN 'http'
                ELSE access_mode
            END
            WHERE transport IS NULL AND access_mode IS NOT NULL
            """
        )
    if "extraction_mode" in column_names and "source_family" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET extraction_mode = CASE source_family
                WHEN 'bulk' THEN 'bulk_snapshot'
                WHEN 'stats' THEN 'incremental_api'
                WHEN 'context' THEN 'context_enrichment'
                WHEN 'fallback' THEN 'html_fallback'
                ELSE extraction_mode
            END
            WHERE extraction_mode IS NULL
            """
        )
    if "default_remote_url" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET default_remote_url = ''
            WHERE default_remote_url IS NULL
            """
        )
    if "owner_note" in column_names and "notes" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET owner_note = notes
            WHERE owner_note IS NULL AND notes IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.source_registry
            SET notes = owner_note
            WHERE notes IS NULL AND owner_note IS NOT NULL
            """
        )
    if "updated_at" in column_names and "created_at" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET updated_at = COALESCE(updated_at, created_at, current_timestamp)
            WHERE updated_at IS NULL
            """
        )


def _backfill_ingest_runs(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
    if "trigger_kind" in column_names and "triggered_by" in column_names:
        con.execute(
            """
            UPDATE meta.ingest_runs
            SET trigger_kind = triggered_by
            WHERE trigger_kind IS NULL AND triggered_by IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.ingest_runs
            SET triggered_by = trigger_kind
            WHERE triggered_by IS NULL AND trigger_kind IS NOT NULL
            """
        )
    if "detail_json" in column_names and "details_json" in column_names:
        con.execute(
            """
            UPDATE meta.ingest_runs
            SET detail_json = details_json
            WHERE detail_json IS NULL AND details_json IS NOT NULL
            """
        )


def _backfill_load_events(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
    if "source_id" in column_names and "source_key" in column_names:
        con.execute(
            """
            UPDATE meta.load_events
            SET source_id = source_key
            WHERE source_id IS NULL AND source_key IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.load_events
            SET source_key = source_id
            WHERE source_key IS NULL AND source_id IS NOT NULL
            """
        )
    if "event_kind" in column_names and "event_status" in column_names:
        con.execute(
            """
            UPDATE meta.load_events
            SET event_kind = event_status
            WHERE event_kind IS NULL AND event_status IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.load_events
            SET event_status = event_kind
            WHERE event_status IS NULL AND event_kind IS NOT NULL
            """
        )
    if "payload_json" in column_names and "detail_json" in column_names:
        con.execute(
            """
            UPDATE meta.load_events
            SET payload_json = detail_json
            WHERE payload_json IS NULL AND detail_json IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.load_events
            SET detail_json = payload_json
            WHERE detail_json IS NULL AND payload_json IS NOT NULL
            """
        )
    if "recorded_at" in column_names and "event_timestamp" in column_names:
        con.execute(
            """
            UPDATE meta.load_events
            SET recorded_at = event_timestamp
            WHERE recorded_at IS NULL AND event_timestamp IS NOT NULL
            """
        )


def _backfill_dq_events(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
    if "dq_rule_code" in column_names and "dq_rule_key" in column_names:
        con.execute(
            """
            UPDATE meta.dq_events
            SET dq_rule_code = dq_rule_key
            WHERE dq_rule_code IS NULL AND dq_rule_key IS NOT NULL
            """
        )
    if "affected_row_count" in column_names and "record_count" in column_names:
        con.execute(
            """
            UPDATE meta.dq_events
            SET affected_row_count = record_count
            WHERE affected_row_count IS NULL AND record_count IS NOT NULL
            """
        )
    if "detail_json" in column_names and "details_json" in column_names:
        con.execute(
            """
            UPDATE meta.dq_events
            SET detail_json = details_json
            WHERE detail_json IS NULL AND details_json IS NOT NULL
            """
        )
    if "recorded_at" in column_names and "event_timestamp" in column_names:
        con.execute(
            """
            UPDATE meta.dq_events
            SET recorded_at = event_timestamp
            WHERE recorded_at IS NULL AND event_timestamp IS NOT NULL
            """
        )


def _backfill_pipeline_state(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
    if "pipeline_name" in column_names and "pipeline_key" in column_names:
        con.execute(
            """
            UPDATE meta.pipeline_state
            SET pipeline_name = pipeline_key
            WHERE pipeline_name IS NULL AND pipeline_key IS NOT NULL
            """
        )
        con.execute(
            """
            UPDATE meta.pipeline_state
            SET pipeline_key = pipeline_name
            WHERE pipeline_key IS NULL AND pipeline_name IS NOT NULL
            """
        )
    if "state_json" in column_names and "details_json" in column_names:
        con.execute(
            """
            UPDATE meta.pipeline_state
            SET state_json = details_json
            WHERE state_json IS NULL AND details_json IS NOT NULL
            """
        )
    if "last_success_at" in column_names and "last_successful_run_at" in column_names:
        con.execute(
            """
            UPDATE meta.pipeline_state
            SET last_success_at = last_successful_run_at
            WHERE last_success_at IS NULL AND last_successful_run_at IS NOT NULL
            """
        )
    if "last_attempt_at" in column_names and "last_attempted_run_at" in column_names:
        con.execute(
            """
            UPDATE meta.pipeline_state
            SET last_attempt_at = last_attempted_run_at
            WHERE last_attempt_at IS NULL AND last_attempted_run_at IS NOT NULL
            """
        )
    if "updated_at" in column_names:
        con.execute(
            """
            UPDATE meta.pipeline_state
            SET updated_at = COALESCE(
                updated_at,
                last_attempt_at,
                last_success_at,
                current_timestamp
            )
            WHERE updated_at IS NULL
            """
        )


def _backfill_legacy_values(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    column_names: set[str],
) -> None:
    if table_name == "source_registry":
        _backfill_source_registry(con, column_names)
    elif table_name == "ingest_runs":
        _backfill_ingest_runs(con, column_names)
    elif table_name == "load_events":
        _backfill_load_events(con, column_names)
    elif table_name == "dq_events":
        _backfill_dq_events(con, column_names)
    elif table_name == "pipeline_state":
        _backfill_pipeline_state(con, column_names)


def ensure_metadata_surface(settings: Settings) -> None:
    con = _connect(settings)
    try:
        for schema_name in SCHEMA_NAMES:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

        for table_name, spec in TABLE_SPECS.items():
            con.execute(
                _create_table_statement(
                    table_name=table_name,
                    primary_key=spec["primary_key"],
                    columns=spec["columns"],
                )
            )
            existing = _add_missing_columns(con, table_name, spec["columns"])
            _backfill_legacy_values(con, table_name, existing)
    finally:
        con.close()


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _new_id() -> str:
    return str(uuid.uuid4())


def _dict_rows(
    cursor: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    result = cursor.execute(sql, params or [])
    cols = [item[0] for item in result.description]
    return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]


def _dict_row(
    cursor: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any] | None = None,
) -> dict[str, Any] | None:
    rows = _dict_rows(cursor, sql, params)
    return rows[0] if rows else None


def seed_default_sources(settings: Settings) -> int:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "source_registry")
        identity_expr = _coalesce_identifier(columns, "source_id", "source_key")
        processed = 0
        for source in DEFAULT_SOURCES:
            existing = con.execute(
                f"SELECT {identity_expr} FROM meta.source_registry WHERE {identity_expr} = ?",
                [source["source_id"]],
            ).fetchone()
            values = [
                ("source_id", source["source_id"]),
                ("source_key", source["source_key"]),
                ("source_name", source["source_name"]),
                ("source_tier", source["source_tier"]),
                ("source_status", source["source_status"]),
                ("source_priority", source["source_priority"]),
                ("source_kind", source["source_kind"]),
                ("source_family", source["source_family"]),
                ("access_mode", source["access_mode"]),
                ("default_frequency", source["default_frequency"]),
                ("landing_zone", source["landing_zone"]),
                ("owner_note", source["owner_note"]),
                ("transport", source["transport"]),
                ("extraction_mode", source["extraction_mode"]),
                ("default_remote_url", source["default_remote_url"]),
                ("notes", source["notes"]),
                ("is_active", source["is_active"]),
            ]
            if existing is None:
                insert_columns: list[str] = []
                params: list[Any] = []
                value_sql: list[str] = []
                for column_name, value in values:
                    if column_name in columns:
                        insert_columns.append(column_name)
                        params.append(value)
                        value_sql.append("?")
                if "updated_at" in columns:
                    insert_columns.append("updated_at")
                    value_sql.append("current_timestamp")
                joined_columns = ", ".join(insert_columns)
                joined_values = ", ".join(value_sql)
                con.execute(
                    f"INSERT INTO meta.source_registry ({joined_columns}) VALUES ({joined_values})",
                    params,
                )
            else:
                updates: list[str] = []
                params = []
                for column_name, value in values:
                    if column_name in columns:
                        updates.append(f"{column_name} = ?")
                        params.append(value)
                if "updated_at" in columns:
                    updates.append("updated_at = current_timestamp")
                params.append(source["source_id"])
                con.execute(
                    (
                        "UPDATE meta.source_registry "
                        f"SET {', '.join(updates)} WHERE {identity_expr} = ?"
                    ),
                    params,
                )
            processed += 1
        return processed
    finally:
        con.close()


def list_sources(settings: Settings) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "source_registry")
        source_id_expr = _coalesce_identifier(columns, "source_id", "source_key")
        rows = _dict_rows(
            con,
            f"""
            SELECT
                {source_id_expr} AS source_id,
                {source_id_expr} AS source_key,
                source_name,
                source_tier,
                source_priority,
                source_kind,
                {_source_transport_expr(columns)} AS transport,
                {_source_extraction_expr(columns)} AS extraction_mode,
                {_source_status_expr(columns)} AS source_status,
                COALESCE(notes, owner_note, '') AS notes,
                COALESCE(default_remote_url, '') AS default_remote_url
            FROM meta.source_registry
            ORDER BY source_priority, {source_id_expr}
            """,
        )
        return rows
    finally:
        con.close()


def get_source(settings: Settings, source_id: str) -> dict[str, Any] | None:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "source_registry")
        source_id_expr = _coalesce_identifier(columns, "source_id", "source_key")
        return _dict_row(
            con,
            f"""
            SELECT
                {source_id_expr} AS source_id,
                {source_id_expr} AS source_key,
                source_name,
                source_tier,
                source_priority,
                source_kind,
                {_source_transport_expr(columns)} AS transport,
                {_source_extraction_expr(columns)} AS extraction_mode,
                {_source_status_expr(columns)} AS source_status,
                COALESCE(notes, owner_note, '') AS notes,
                COALESCE(default_remote_url, '') AS default_remote_url
            FROM meta.source_registry
            WHERE {source_id_expr} = ?
            """,
            [source_id],
        )
    finally:
        con.close()


def upsert_pipeline_state(
    settings: Settings,
    pipeline_name: str,
    last_run_status: str,
    state_json: str,
    *,
    mark_success: bool,
) -> None:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "pipeline_state")
        identity_expr = _coalesce_identifier(columns, "pipeline_name", "pipeline_key")
        existing = con.execute(
            f"SELECT {identity_expr} FROM meta.pipeline_state WHERE {identity_expr} = ?",
            [pipeline_name],
        ).fetchone()
        now_fields = {"last_attempt_at"}
        if mark_success:
            now_fields.add("last_success_at")
        if existing is None:
            insert_columns: list[str] = []
            params: list[Any] = []
            value_sql: list[str] = []
            field_values = [
                ("pipeline_name", pipeline_name),
                ("pipeline_key", pipeline_name),
                ("last_run_status", last_run_status),
                ("state_json", state_json),
            ]
            for column_name, value in field_values:
                if column_name in columns:
                    insert_columns.append(column_name)
                    params.append(value)
                    value_sql.append("?")
            for column_name in sorted(now_fields):
                if column_name in columns:
                    insert_columns.append(column_name)
                    value_sql.append("current_timestamp")
            if "updated_at" in columns:
                insert_columns.append("updated_at")
                value_sql.append("current_timestamp")
            joined_columns = ", ".join(insert_columns)
            joined_values = ", ".join(value_sql)
            con.execute(
                f"INSERT INTO meta.pipeline_state ({joined_columns}) VALUES ({joined_values})",
                params,
            )
        else:
            updates = []
            params = []
            for column_name, value in (
                ("pipeline_key", pipeline_name),
                ("last_run_status", last_run_status),
                ("state_json", state_json),
            ):
                if column_name in columns:
                    updates.append(f"{column_name} = ?")
                    params.append(value)
            for column_name in sorted(now_fields):
                if column_name in columns:
                    updates.append(f"{column_name} = current_timestamp")
            if "updated_at" in columns:
                updates.append("updated_at = current_timestamp")
            params.append(pipeline_name)
            con.execute(
                (
                    "UPDATE meta.pipeline_state "
                    f"SET {', '.join(updates)} WHERE {identity_expr} = ?"
                ),
                params,
            )
    finally:
        con.close()


def get_pipeline_state(settings: Settings, pipeline_name: str) -> dict[str, Any] | None:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "pipeline_state")
        identity_expr = _coalesce_identifier(columns, "pipeline_name", "pipeline_key")
        row = con.execute(
            f"""
            SELECT
                {identity_expr} AS pipeline_name,
                last_run_status,
                state_json
            FROM meta.pipeline_state
            WHERE {identity_expr} = ?
            """,
            [pipeline_name],
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return {
        "pipeline_name": row[0],
        "last_run_status": row[1],
        "state_json": row[2],
    }


def start_ingest_run(
    settings: Settings,
    pipeline_name: str,
    triggered_by: str,
    run_mode: str = "manual",
    detail_json: str | None = None,
    *,
    adapter_id: str | None = None,
) -> str:
    ensure_metadata_surface(settings)
    ingest_run_id = _new_id()
    con = _connect(settings)
    try:
        columns = _column_names(con, "ingest_runs")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("ingest_run_id", ingest_run_id),
            ("pipeline_name", pipeline_name),
            ("adapter_id", adapter_id),
            ("run_status", "started"),
            ("triggered_by", triggered_by),
            ("trigger_kind", triggered_by),
            ("run_mode", run_mode),
            ("detail_json", detail_json),
        ]
        for column_name, value in field_values:
            if column_name in columns:
                insert_columns.append(column_name)
                params.append(value)
        joined_columns = ", ".join(insert_columns)
        placeholders = ", ".join(["?"] * len(insert_columns))
        con.execute(
            f"INSERT INTO meta.ingest_runs ({joined_columns}) VALUES ({placeholders})",
            params,
        )
    finally:
        con.close()
    return ingest_run_id


def finish_ingest_run(
    settings: Settings,
    ingest_run_id: str,
    run_status: str,
    detail_json: str | None = None,
    *,
    message: str | None = None,
) -> None:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "ingest_runs")
        updates = ["run_status = ?", "finished_at = current_timestamp"]
        params: list[Any] = [run_status]
        if "detail_json" in columns:
            updates.append("detail_json = ?")
            params.append(detail_json)
        if "message" in columns:
            updates.append("message = ?")
            params.append(message)
        params.append(ingest_run_id)
        con.execute(
            f"UPDATE meta.ingest_runs SET {', '.join(updates)} WHERE ingest_run_id = ?",
            params,
        )
    finally:
        con.close()


def create_ingest_run(
    settings: Settings,
    *,
    pipeline_name: str,
    adapter_id: str,
    run_mode: str,
    run_status: str,
    trigger_kind: str,
    landing_dir: str,
    manifest_path: str,
    receipt_path: str,
    asset_count: int,
    landed_file_count: int,
    message: str,
) -> str:
    ingest_run_id = start_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        triggered_by=trigger_kind,
        run_mode=run_mode,
        detail_json=_json_dumps(
            {
                "adapter_id": adapter_id,
                "landing_dir": landing_dir,
                "manifest_path": manifest_path,
                "receipt_path": receipt_path,
                "asset_count": asset_count,
                "landed_file_count": landed_file_count,
            }
        ),
        adapter_id=adapter_id,
    )
    con = _connect(settings)
    try:
        columns = _column_names(con, "ingest_runs")
        updates = ["run_status = ?", "finished_at = current_timestamp"]
        params: list[Any] = [run_status]
        for column_name, value in (
            ("adapter_id", adapter_id),
            ("triggered_by", trigger_kind),
            ("trigger_kind", trigger_kind),
            ("run_mode", run_mode),
            ("landing_dir", landing_dir),
            ("manifest_path", manifest_path),
            ("receipt_path", receipt_path),
            ("asset_count", asset_count),
            ("landed_file_count", landed_file_count),
            ("message", message),
        ):
            if column_name in columns:
                updates.append(f"{column_name} = ?")
                params.append(value)
        params.append(ingest_run_id)
        con.execute(
            f"UPDATE meta.ingest_runs SET {', '.join(updates)} WHERE ingest_run_id = ?",
            params,
        )
    finally:
        con.close()
    return ingest_run_id


def list_ingest_runs(
    settings: Settings,
    pipeline_name: str | None = None,
) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "ingest_runs")
        trigger_expr = _coalesce_identifier(columns, "trigger_kind", "triggered_by")
        where_sql = ""
        params: list[Any] = []
        if pipeline_name is not None:
            where_sql = "WHERE pipeline_name = ?"
            params.append(pipeline_name)
        rows = con.execute(
            f"""
            SELECT
                ingest_run_id,
                pipeline_name,
                run_status,
                {trigger_expr} AS trigger_kind,
                {trigger_expr} AS triggered_by,
                run_mode,
                detail_json,
                started_at,
                finished_at
            FROM meta.ingest_runs
            {where_sql}
            ORDER BY started_at DESC, ingest_run_id DESC
            """,
            params,
        ).fetchall()
    finally:
        con.close()
    keys = [
        "ingest_run_id",
        "pipeline_name",
        "run_status",
        "trigger_kind",
        "triggered_by",
        "run_mode",
        "detail_json",
        "started_at",
        "finished_at",
    ]
    return [dict(zip(keys, row, strict=False)) for row in rows]


def record_load_event(
    settings: Settings,
    *,
    ingest_run_id: str,
    source_id: str | None = None,
    target_schema: str | None = None,
    target_object: str | None = None,
    row_count: int | None = None,
    event_status: str | None = None,
    detail_json: str | None = None,
    pipeline_name: str | None = None,
    event_kind: str | None = None,
    object_path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    ensure_metadata_surface(settings)
    load_event_id = _new_id()
    event_kind = event_kind or event_status
    event_status = event_status or event_kind
    detail_json = detail_json or (_json_dumps(payload) if payload is not None else None)
    con = _connect(settings)
    try:
        columns = _column_names(con, "load_events")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("load_event_id", load_event_id),
            ("ingest_run_id", ingest_run_id),
            ("source_id", source_id),
            ("source_key", source_id),
            ("pipeline_name", pipeline_name),
            ("event_kind", event_kind),
            ("target_schema", target_schema),
            ("target_object", target_object),
            ("object_path", object_path),
            ("row_count", row_count),
            ("event_status", event_status),
            ("payload_json", detail_json),
            ("detail_json", detail_json),
        ]
        for column_name, value in field_values:
            if column_name in columns:
                insert_columns.append(column_name)
                params.append(value)
        joined_columns = ", ".join(insert_columns)
        placeholders = ", ".join(["?"] * len(insert_columns))
        con.execute(
            f"INSERT INTO meta.load_events ({joined_columns}) VALUES ({placeholders})",
            params,
        )
    finally:
        con.close()
    return load_event_id


def list_load_events(
    settings: Settings,
    ingest_run_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        columns = _column_names(con, "load_events")
        where_sql = ""
        params: list[Any] = []
        if ingest_run_id is not None:
            where_sql = "WHERE ingest_run_id = ?"
            params.append(ingest_run_id)
        source_expr = _coalesce_identifier(columns, "source_id", "source_key")
        rows = con.execute(
            f"""
            SELECT
                load_event_id,
                ingest_run_id,
                {source_expr} AS source_id,
                pipeline_name,
                event_kind,
                target_schema,
                target_object,
                object_path,
                row_count,
                event_status,
                COALESCE(payload_json, detail_json) AS detail_json,
                recorded_at
            FROM meta.load_events
            {where_sql}
            ORDER BY recorded_at DESC, load_event_id DESC
            """,
            params,
        ).fetchall()
    finally:
        con.close()
    keys = [
        "load_event_id",
        "ingest_run_id",
        "source_id",
        "pipeline_name",
        "event_kind",
        "target_schema",
        "target_object",
        "object_path",
        "row_count",
        "event_status",
        "detail_json",
        "recorded_at",
    ]
    return [dict(zip(keys, row, strict=False)) for row in rows]


def record_dq_event(
    settings: Settings,
    ingest_run_id: str,
    source_id: str,
    severity: str,
    dq_rule_code: str,
    target_schema: str,
    target_object: str,
    affected_row_count: int,
    detail_json: str | None = None,
) -> str:
    ensure_metadata_surface(settings)
    dq_event_id = _new_id()
    con = _connect(settings)
    try:
        columns = _column_names(con, "dq_events")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("dq_event_id", dq_event_id),
            ("ingest_run_id", ingest_run_id),
            ("source_id", source_id),
            ("severity", severity),
            ("dq_rule_code", dq_rule_code),
            ("target_schema", target_schema),
            ("target_object", target_object),
            ("affected_row_count", affected_row_count),
            ("detail_json", detail_json),
        ]
        for column_name, value in field_values:
            if column_name in columns:
                insert_columns.append(column_name)
                params.append(value)
        joined_columns = ", ".join(insert_columns)
        placeholders = ", ".join(["?"] * len(insert_columns))
        con.execute(
            f"INSERT INTO meta.dq_events ({joined_columns}) VALUES ({placeholders})",
            params,
        )
    finally:
        con.close()
    return dq_event_id


def record_source_file(
    settings: Settings,
    *,
    ingest_run_id: str,
    adapter_id: str,
    source_url: str,
    local_path: str,
    file_size_bytes: int,
    sha256_hex: str,
) -> str:
    ensure_metadata_surface(settings)
    source_file_id = _new_id()
    con = _connect(settings)
    try:
        columns = _column_names(con, "source_files")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("source_file_id", source_file_id),
            ("ingest_run_id", ingest_run_id),
            ("adapter_id", adapter_id),
            ("source_url", source_url),
            ("local_path", local_path),
            ("file_size_bytes", file_size_bytes),
            ("sha256_hex", sha256_hex),
        ]
        for column_name, value in field_values:
            if column_name in columns:
                insert_columns.append(column_name)
                params.append(value)
        joined_columns = ", ".join(insert_columns)
        placeholders = ", ".join(["?"] * len(insert_columns))
        con.execute(
            f"INSERT INTO meta.source_files ({joined_columns}) VALUES ({placeholders})",
            params,
        )
    finally:
        con.close()
    return source_file_id




def latest_source_file(settings: Settings, adapter_id: str) -> dict[str, Any] | None:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        rows = _dict_rows(
            con,
            """
            SELECT
                source_file_id,
                ingest_run_id,
                adapter_id,
                source_url,
                local_path,
                file_size_bytes,
                sha256_hex,
                created_at
            FROM meta.source_files
            WHERE adapter_id = ?
            ORDER BY created_at DESC, source_file_id DESC
            LIMIT 1
            """,
            [adapter_id],
        )
        return rows[0] if rows else None
    finally:
        con.close()


def stage_table_row_count(settings: Settings, qualified_table: str) -> int:
    con = _connect(settings)
    try:
        row = con.execute(f"SELECT COUNT(*) FROM {qualified_table}").fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def load_csv_into_stage_table(
    settings: Settings,
    *,
    csv_path: str,
    qualified_table: str,
    source_file_id: str,
    adapter_id: str,
) -> int:
    con = _connect(settings)
    try:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {qualified_table} AS
            SELECT
                src.*,
                ? AS _source_file_id,
                ? AS _source_file_path,
                ? AS _adapter_id,
                current_timestamp AS _loaded_at
            FROM read_csv_auto(?, HEADER=TRUE, ALL_VARCHAR=TRUE) AS src
            """,
            [source_file_id, csv_path, adapter_id, csv_path],
        )
        row = con.execute(f"SELECT COUNT(*) FROM {qualified_table}").fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def compute_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
