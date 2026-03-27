from __future__ import annotations

import duckdb

from new_nfl.settings import Settings

SCHEMA_NAMES = ("meta", "raw", "stg", "core", "mart", "feat", "sim", "scratch")

META_TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS meta.source_registry (
        source_id VARCHAR PRIMARY KEY,
        source_name VARCHAR NOT NULL,
        source_tier VARCHAR NOT NULL,
        source_status VARCHAR NOT NULL,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta.ingest_runs (
        ingest_run_id VARCHAR PRIMARY KEY,
        pipeline_name VARCHAR NOT NULL,
        run_status VARCHAR NOT NULL,
        started_at TIMESTAMP DEFAULT current_timestamp,
        finished_at TIMESTAMP,
        detail_json VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta.load_events (
        load_event_id VARCHAR PRIMARY KEY,
        ingest_run_id VARCHAR,
        target_schema VARCHAR NOT NULL,
        target_object VARCHAR NOT NULL,
        row_count BIGINT,
        event_status VARCHAR NOT NULL,
        recorded_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta.dq_events (
        dq_event_id VARCHAR PRIMARY KEY,
        ingest_run_id VARCHAR,
        severity VARCHAR NOT NULL,
        dq_rule_code VARCHAR NOT NULL,
        object_name VARCHAR,
        detail_json VARCHAR,
        recorded_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta.pipeline_state (
        pipeline_name VARCHAR PRIMARY KEY,
        state_json VARCHAR,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
)


def bootstrap_local_environment(settings: Settings) -> None:
    settings.data_root.mkdir(parents=True, exist_ok=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(settings.db_path))
    try:
        for schema_name in SCHEMA_NAMES:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

        for statement in META_TABLE_STATEMENTS:
            con.execute(statement)
    finally:
        con.close()
