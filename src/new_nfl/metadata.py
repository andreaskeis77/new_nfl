from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import duckdb

from new_nfl.settings import Settings

SCHEMA_NAMES = ("meta", "raw", "stg", "core", "mart", "feat", "sim", "scratch")

TABLE_SPECS = {
    "source_registry": {
        "primary_key": "source_id",
        "columns": {
            "source_id": "VARCHAR",
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
            "created_at": "TIMESTAMP DEFAULT current_timestamp",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
    "ingest_runs": {
        "primary_key": "ingest_run_id",
        "columns": {
            "ingest_run_id": "VARCHAR",
            "pipeline_name": "VARCHAR NOT NULL",
            "run_status": "VARCHAR NOT NULL",
            "triggered_by": "VARCHAR",
            "run_mode": "VARCHAR",
            "started_at": "TIMESTAMP DEFAULT current_timestamp",
            "finished_at": "TIMESTAMP",
            "detail_json": "VARCHAR",
        },
    },
    "load_events": {
        "primary_key": "load_event_id",
        "columns": {
            "load_event_id": "VARCHAR",
            "ingest_run_id": "VARCHAR",
            "source_id": "VARCHAR",
            "target_schema": "VARCHAR NOT NULL",
            "target_object": "VARCHAR NOT NULL",
            "row_count": "BIGINT",
            "event_status": "VARCHAR NOT NULL",
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
            "last_run_status": "VARCHAR",
            "last_success_at": "TIMESTAMP",
            "last_attempt_at": "TIMESTAMP",
            "state_json": "VARCHAR",
            "updated_at": "TIMESTAMP DEFAULT current_timestamp",
        },
    },
}


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    source_name: str
    source_tier: str
    source_status: str
    source_priority: int
    source_kind: str
    source_family: str
    access_mode: str
    default_frequency: str
    landing_zone: str
    owner_note: str


DEFAULT_SOURCES = (
    SourceDefinition(
        source_id="nflverse_bulk",
        source_name="nflverse bulk datasets",
        source_tier="A",
        source_status="candidate",
        source_priority=10,
        source_kind="dataset",
        source_family="bulk",
        access_mode="http",
        default_frequency="daily",
        landing_zone="raw",
        owner_note="Primary bulk candidate for schedules, rosters, and historical stats.",
    ),
    SourceDefinition(
        source_id="official_context_web",
        source_name="official context web source",
        source_tier="B",
        source_status="candidate",
        source_priority=20,
        source_kind="web",
        source_family="context",
        access_mode="html",
        default_frequency="daily",
        landing_zone="raw",
        owner_note="Secondary context source for official schedule and status confirmation.",
    ),
    SourceDefinition(
        source_id="public_stats_api",
        source_name="public stats api candidate",
        source_tier="B",
        source_status="candidate",
        source_priority=30,
        source_kind="api",
        source_family="stats",
        access_mode="json",
        default_frequency="daily",
        landing_zone="raw",
        owner_note="Secondary structured source for near-current stats and cross-checks.",
    ),
    SourceDefinition(
        source_id="reference_html_fallback",
        source_name="reference html fallback",
        source_tier="C",
        source_status="candidate",
        source_priority=90,
        source_kind="web",
        source_family="fallback",
        access_mode="html",
        default_frequency="on-demand",
        landing_zone="raw",
        owner_note="Fallback source class when structured sources are incomplete or delayed.",
    ),
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


def _create_table_statement(table_name: str, primary_key: str, columns: dict[str, str]) -> str:
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
            existing = _column_names(con, table_name)
            for column_name, column_sql in spec["columns"].items():
                if column_name not in existing:
                    alter_type = column_sql.split()[0]
                    con.execute(
                        f"ALTER TABLE meta.{table_name} ADD COLUMN {column_name} {alter_type}"
                    )
    finally:
        con.close()


def seed_default_sources(settings: Settings) -> int:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        for source in DEFAULT_SOURCES:
            existing = con.execute(
                "SELECT 1 FROM meta.source_registry WHERE source_id = ?",
                [source.source_id],
            ).fetchone()
            if existing:
                con.execute(
                    """
                    UPDATE meta.source_registry
                    SET source_name = ?,
                        source_tier = ?,
                        source_status = ?,
                        source_priority = ?,
                        source_kind = ?,
                        source_family = ?,
                        access_mode = ?,
                        default_frequency = ?,
                        landing_zone = ?,
                        owner_note = ?,
                        updated_at = current_timestamp
                    WHERE source_id = ?
                    """,
                    [
                        source.source_name,
                        source.source_tier,
                        source.source_status,
                        source.source_priority,
                        source.source_kind,
                        source.source_family,
                        source.access_mode,
                        source.default_frequency,
                        source.landing_zone,
                        source.owner_note,
                        source.source_id,
                    ],
                )
            else:
                con.execute(
                    """
                    INSERT INTO meta.source_registry (
                        source_id,
                        source_name,
                        source_tier,
                        source_status,
                        source_priority,
                        source_kind,
                        source_family,
                        access_mode,
                        default_frequency,
                        landing_zone,
                        owner_note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        source.source_id,
                        source.source_name,
                        source.source_tier,
                        source.source_status,
                        source.source_priority,
                        source.source_kind,
                        source.source_family,
                        source.access_mode,
                        source.default_frequency,
                        source.landing_zone,
                        source.owner_note,
                    ],
                )
    finally:
        con.close()

    return len(DEFAULT_SOURCES)


def list_sources(settings: Settings) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        rows = con.execute(
            """
            SELECT
                source_id,
                source_name,
                source_tier,
                source_status,
                source_priority,
                source_kind,
                source_family,
                access_mode,
                default_frequency,
                landing_zone,
                owner_note
            FROM meta.source_registry
            ORDER BY source_priority, source_id
            """
        ).fetchall()
    finally:
        con.close()

    keys = [
        "source_id",
        "source_name",
        "source_tier",
        "source_status",
        "source_priority",
        "source_kind",
        "source_family",
        "access_mode",
        "default_frequency",
        "landing_zone",
        "owner_note",
    ]
    return [dict(zip(keys, row, strict=False)) for row in rows]


def upsert_pipeline_state(
    settings: Settings,
    pipeline_name: str,
    last_run_status: str,
    state_json: str | None = None,
    mark_success: bool = False,
) -> None:
    ensure_metadata_surface(settings)
    state_payload = state_json if state_json is not None else "{}"

    con = _connect(settings)
    try:
        existing = con.execute(
            "SELECT 1 FROM meta.pipeline_state WHERE pipeline_name = ?",
            [pipeline_name],
        ).fetchone()
        if existing:
            if mark_success:
                con.execute(
                    """
                    UPDATE meta.pipeline_state
                    SET last_run_status = ?,
                        last_attempt_at = current_timestamp,
                        last_success_at = current_timestamp,
                        state_json = ?,
                        updated_at = current_timestamp
                    WHERE pipeline_name = ?
                    """,
                    [last_run_status, state_payload, pipeline_name],
                )
            else:
                con.execute(
                    """
                    UPDATE meta.pipeline_state
                    SET last_run_status = ?,
                        last_attempt_at = current_timestamp,
                        state_json = ?,
                        updated_at = current_timestamp
                    WHERE pipeline_name = ?
                    """,
                    [last_run_status, state_payload, pipeline_name],
                )
        else:
            if mark_success:
                con.execute(
                    """
                    INSERT INTO meta.pipeline_state (
                        pipeline_name,
                        last_run_status,
                        last_attempt_at,
                        last_success_at,
                        state_json
                    ) VALUES (?, ?, current_timestamp, current_timestamp, ?)
                    """,
                    [pipeline_name, last_run_status, state_payload],
                )
            else:
                con.execute(
                    """
                    INSERT INTO meta.pipeline_state (
                        pipeline_name,
                        last_run_status,
                        last_attempt_at,
                        state_json
                    ) VALUES (?, ?, current_timestamp, ?)
                    """,
                    [pipeline_name, last_run_status, state_payload],
                )
    finally:
        con.close()


def get_pipeline_state(settings: Settings, pipeline_name: str) -> dict[str, Any] | None:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        row = con.execute(
            """
            SELECT pipeline_name, last_run_status, state_json
            FROM meta.pipeline_state
            WHERE pipeline_name = ?
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
) -> str:
    ensure_metadata_surface(settings)
    ingest_run_id = str(uuid.uuid4())

    con = _connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.ingest_runs (
                ingest_run_id,
                pipeline_name,
                run_status,
                triggered_by,
                run_mode,
                detail_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ingest_run_id,
                pipeline_name,
                "started",
                triggered_by,
                run_mode,
                detail_json,
            ],
        )
    finally:
        con.close()

    return ingest_run_id


def finish_ingest_run(
    settings: Settings,
    ingest_run_id: str,
    run_status: str,
    detail_json: str | None = None,
) -> None:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        con.execute(
            """
            UPDATE meta.ingest_runs
            SET run_status = ?,
                finished_at = current_timestamp,
                detail_json = ?
            WHERE ingest_run_id = ?
            """,
            [run_status, detail_json, ingest_run_id],
        )
    finally:
        con.close()


def record_load_event(
    settings: Settings,
    ingest_run_id: str,
    source_id: str,
    target_schema: str,
    target_object: str,
    row_count: int,
    event_status: str,
    detail_json: str | None = None,
) -> str:
    ensure_metadata_surface(settings)
    load_event_id = str(uuid.uuid4())

    con = _connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.load_events (
                load_event_id,
                ingest_run_id,
                source_id,
                target_schema,
                target_object,
                row_count,
                event_status,
                detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                load_event_id,
                ingest_run_id,
                source_id,
                target_schema,
                target_object,
                row_count,
                event_status,
                detail_json,
            ],
        )
    finally:
        con.close()

    return load_event_id


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
    dq_event_id = str(uuid.uuid4())

    con = _connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.dq_events (
                dq_event_id,
                ingest_run_id,
                source_id,
                severity,
                dq_rule_code,
                target_schema,
                target_object,
                affected_row_count,
                detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                dq_event_id,
                ingest_run_id,
                source_id,
                severity,
                dq_rule_code,
                target_schema,
                target_object,
                affected_row_count,
                detail_json,
            ],
        )
    finally:
        con.close()

    return dq_event_id
