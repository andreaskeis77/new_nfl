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


def _add_missing_columns(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    columns: dict[str, str],
) -> set[str]:
    existing = _column_names(con, table_name)
    for column_name, column_sql in columns.items():
        if column_name not in existing:
            alter_type = column_sql.split()[0]
            con.execute(f"ALTER TABLE meta.{table_name} ADD COLUMN {column_name} {alter_type}")
    return _column_names(con, table_name)


def _coalesce_identifier(column_names: set[str], modern: str, legacy: str) -> str:
    if modern in column_names and legacy in column_names:
        return f"COALESCE({modern}, {legacy})"
    if modern in column_names:
        return modern
    return legacy


def _backfill_source_registry(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
    if "source_id" in column_names and "source_key" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET source_id = source_key
            WHERE source_id IS NULL AND source_key IS NOT NULL
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
    if "default_frequency" in column_names and "update_frequency" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET default_frequency = update_frequency
            WHERE default_frequency IS NULL AND update_frequency IS NOT NULL
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
    if "updated_at" in column_names and "created_at" in column_names:
        con.execute(
            """
            UPDATE meta.source_registry
            SET updated_at = COALESCE(updated_at, created_at, current_timestamp)
            WHERE updated_at IS NULL
            """
        )


def _backfill_ingest_runs(con: duckdb.DuckDBPyConnection, column_names: set[str]) -> None:
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
    if "detail_json" in column_names and "details_json" in column_names:
        con.execute(
            """
            UPDATE meta.load_events
            SET detail_json = details_json
            WHERE detail_json IS NULL AND details_json IS NOT NULL
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


def seed_default_sources(settings: Settings) -> int:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        columns = _column_names(con, "source_registry")
        identity_expr = _coalesce_identifier(columns, "source_id", "source_key")
        for source in DEFAULT_SOURCES:
            existing = con.execute(
                f"SELECT 1 FROM meta.source_registry WHERE {identity_expr} = ?",
                [source.source_id],
            ).fetchone()
            if existing:
                updates: list[str] = []
                params: list[Any] = []
                field_values = {
                    "source_id": source.source_id,
                    "source_key": source.source_id,
                    "source_name": source.source_name,
                    "source_tier": source.source_tier,
                    "source_status": source.source_status,
                    "source_priority": source.source_priority,
                    "source_kind": source.source_kind,
                    "source_family": source.source_family,
                    "access_mode": source.access_mode,
                    "default_frequency": source.default_frequency,
                    "update_frequency": source.default_frequency,
                    "landing_zone": source.landing_zone,
                    "owner_note": source.owner_note,
                    "notes": source.owner_note,
                }
                for column_name, value in field_values.items():
                    if column_name in columns:
                        updates.append(f"{column_name} = ?")
                        params.append(value)
                if "is_active" in columns:
                    updates.append("is_active = ?")
                    params.append(True)
                if "updated_at" in columns:
                    updates.append("updated_at = current_timestamp")
                params.append(source.source_id)
                update_sql = (
                    f"UPDATE meta.source_registry SET {', '.join(updates)} "
                    f"WHERE {identity_expr} = ?"
                )
                con.execute(update_sql, params)
            else:
                insert_columns: list[str] = []
                params: list[Any] = []
                field_values = [
                    ("source_id", source.source_id),
                    ("source_key", source.source_id),
                    ("source_name", source.source_name),
                    ("source_tier", source.source_tier),
                    ("source_status", source.source_status),
                    ("source_priority", source.source_priority),
                    ("source_kind", source.source_kind),
                    ("source_family", source.source_family),
                    ("access_mode", source.access_mode),
                    ("default_frequency", source.default_frequency),
                    ("update_frequency", source.default_frequency),
                    ("landing_zone", source.landing_zone),
                    ("owner_note", source.owner_note),
                    ("notes", source.owner_note),
                ]
                for column_name, value in field_values:
                    if column_name in columns:
                        insert_columns.append(column_name)
                        params.append(value)
                if "is_active" in columns:
                    insert_columns.append("is_active")
                    params.append(True)
                placeholders = ", ".join(["?"] * len(insert_columns))
                joined_columns = ", ".join(insert_columns)
                con.execute(
                    f"INSERT INTO meta.source_registry ({joined_columns}) VALUES ({placeholders})",
                    params,
                )
    finally:
        con.close()

    return len(DEFAULT_SOURCES)


def list_sources(settings: Settings) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        columns = _column_names(con, "source_registry")
        rows = con.execute(
            f"""
            SELECT
                {_coalesce_identifier(columns, 'source_id', 'source_key')} AS source_id,
                source_name,
                source_tier,
                COALESCE(
                    source_status,
                    CASE
                        WHEN {'is_active' if 'is_active' in columns else 'NULL'}
                        THEN 'candidate'
                        ELSE 'inactive'
                    END,
                    'candidate'
                ) AS source_status,
                source_priority,
                source_kind,
                {'source_family' if 'source_family' in columns else 'NULL'} AS source_family,
                {'access_mode' if 'access_mode' in columns else 'NULL'} AS access_mode,
                COALESCE(
                    {'default_frequency' if 'default_frequency' in columns else 'NULL'},
                    {'update_frequency' if 'update_frequency' in columns else 'NULL'}
                ) AS default_frequency,
                {'landing_zone' if 'landing_zone' in columns else 'NULL'} AS landing_zone,
                COALESCE(
                    {'owner_note' if 'owner_note' in columns else 'NULL'},
                    {'notes' if 'notes' in columns else 'NULL'}
                ) AS owner_note
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
        columns = _column_names(con, "pipeline_state")
        identity_expr = _coalesce_identifier(columns, "pipeline_name", "pipeline_key")
        existing = con.execute(
            f"SELECT 1 FROM meta.pipeline_state WHERE {identity_expr} = ?",
            [pipeline_name],
        ).fetchone()
        if existing:
            updates: list[str] = []
            params: list[Any] = []
            field_values = {
                "pipeline_name": pipeline_name,
                "pipeline_key": pipeline_name,
                "last_run_status": last_run_status,
                "state_json": state_payload,
                "details_json": state_payload,
            }
            for column_name, value in field_values.items():
                if column_name in columns:
                    updates.append(f"{column_name} = ?")
                    params.append(value)
            if "last_attempt_at" in columns:
                updates.append("last_attempt_at = current_timestamp")
            if "last_attempted_run_at" in columns:
                updates.append("last_attempted_run_at = current_timestamp")
            if mark_success:
                if "last_success_at" in columns:
                    updates.append("last_success_at = current_timestamp")
                if "last_successful_run_at" in columns:
                    updates.append("last_successful_run_at = current_timestamp")
            if "updated_at" in columns:
                updates.append("updated_at = current_timestamp")
            params.append(pipeline_name)
            con.execute(
                f"UPDATE meta.pipeline_state SET {', '.join(updates)} WHERE {identity_expr} = ?",
                params,
            )
        else:
            insert_columns: list[str] = []
            params: list[Any] = []
            field_values = [
                ("pipeline_name", pipeline_name),
                ("pipeline_key", pipeline_name),
                ("last_run_status", last_run_status),
                ("state_json", state_payload),
                ("details_json", state_payload),
            ]
            for column_name, value in field_values:
                if column_name in columns:
                    insert_columns.append(column_name)
                    params.append(value)
            if "last_attempt_at" in columns:
                insert_columns.append("last_attempt_at")
            if "last_attempted_run_at" in columns:
                insert_columns.append("last_attempted_run_at")
            if mark_success and "last_success_at" in columns:
                insert_columns.append("last_success_at")
            if mark_success and "last_successful_run_at" in columns:
                insert_columns.append("last_successful_run_at")
            timestamp_columns = {
                "last_attempt_at",
                "last_attempted_run_at",
                "last_success_at",
                "last_successful_run_at",
            }
            value_sql = []
            for col in insert_columns:
                if col in timestamp_columns:
                    value_sql.append("current_timestamp")
                else:
                    value_sql.append("?")
            joined_columns = ", ".join(insert_columns)
            joined_values = ", ".join(value_sql)
            con.execute(
                f"INSERT INTO meta.pipeline_state ({joined_columns}) VALUES ({joined_values})",
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
                COALESCE(
                    {'state_json' if 'state_json' in columns else 'NULL'},
                    {'details_json' if 'details_json' in columns else 'NULL'}
                ) AS state_json
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
) -> str:
    ensure_metadata_surface(settings)
    ingest_run_id = str(uuid.uuid4())

    con = _connect(settings)
    try:
        columns = _column_names(con, "ingest_runs")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("ingest_run_id", ingest_run_id),
            ("pipeline_name", pipeline_name),
            ("run_status", "started"),
            ("triggered_by", triggered_by),
            ("run_mode", run_mode),
            ("detail_json", detail_json),
            ("details_json", detail_json),
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
        if "details_json" in columns:
            updates.append("details_json = ?")
            params.append(detail_json)
        params.append(ingest_run_id)
        con.execute(
            f"UPDATE meta.ingest_runs SET {', '.join(updates)} WHERE ingest_run_id = ?",
            params,
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
        columns = _column_names(con, "load_events")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("load_event_id", load_event_id),
            ("ingest_run_id", ingest_run_id),
            ("source_id", source_id),
            ("source_key", source_id),
            ("target_schema", target_schema),
            ("target_object", target_object),
            ("row_count", row_count),
            ("event_status", event_status),
            ("detail_json", detail_json),
            ("details_json", detail_json),
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
        columns = _column_names(con, "dq_events")
        insert_columns: list[str] = []
        params: list[Any] = []
        field_values = [
            ("dq_event_id", dq_event_id),
            ("ingest_run_id", ingest_run_id),
            ("source_id", source_id),
            ("severity", severity),
            ("dq_rule_code", dq_rule_code),
            ("dq_rule_key", dq_rule_code),
            ("target_schema", target_schema),
            ("target_object", target_object),
            ("affected_row_count", affected_row_count),
            ("record_count", affected_row_count),
            ("detail_json", detail_json),
            ("details_json", detail_json),
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


def list_ingest_runs(
    settings: Settings,
    pipeline_name: str | None = None,
) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        columns = _column_names(con, 'ingest_runs')
        where_sql = ''
        params: list[Any] = []
        if pipeline_name is not None:
            where_sql = 'WHERE pipeline_name = ?'
            params.append(pipeline_name)
        rows = con.execute(
            f"""
            SELECT
                ingest_run_id,
                pipeline_name,
                run_status,
                triggered_by,
                run_mode,
                COALESCE(
                    {'detail_json' if 'detail_json' in columns else 'NULL'},
                    {'details_json' if 'details_json' in columns else 'NULL'}
                ) AS detail_json,
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
        'ingest_run_id',
        'pipeline_name',
        'run_status',
        'triggered_by',
        'run_mode',
        'detail_json',
        'started_at',
        'finished_at',
    ]
    return [dict(zip(keys, row, strict=False)) for row in rows]


def list_load_events(
    settings: Settings,
    ingest_run_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_metadata_surface(settings)

    con = _connect(settings)
    try:
        columns = _column_names(con, 'load_events')
        where_sql = ''
        params: list[Any] = []
        if ingest_run_id is not None:
            where_sql = 'WHERE ingest_run_id = ?'
            params.append(ingest_run_id)
        source_identity = _coalesce_identifier(columns, 'source_id', 'source_key')
        rows = con.execute(
            f"""
            SELECT
                load_event_id,
                ingest_run_id,
                {source_identity} AS source_id,
                target_schema,
                target_object,
                row_count,
                event_status,
                COALESCE(
                    {'detail_json' if 'detail_json' in columns else 'NULL'},
                    {'details_json' if 'details_json' in columns else 'NULL'}
                ) AS detail_json,
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
        'load_event_id',
        'ingest_run_id',
        'source_id',
        'target_schema',
        'target_object',
        'row_count',
        'event_status',
        'detail_json',
        'recorded_at',
    ]
    return [dict(zip(keys, row, strict=False)) for row in rows]
