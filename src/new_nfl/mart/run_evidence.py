"""Mart builder for run evidence (T2.6H, ADR-0029).

Three projections are built in a single pass — they all derive from the
same ``meta.*`` evidence surface and always need to stay in sync:

* ``mart.run_overview_v1`` — one row per ``meta.job_run`` enriched with
  ``meta.job_definition`` (``job_key``, ``job_type``) and aggregated
  counts from ``meta.run_event`` / ``meta.run_artifact``. Adds the
  derived columns ``duration_seconds`` (from ``finished_at - started_at``)
  and ``last_event_recorded_at`` (the newest event timestamp per run).

* ``mart.run_event_v1`` — passthrough of ``meta.run_event`` with
  ``job_run_id_lower`` / ``run_event_id_lower`` shadow columns for
  case-insensitive lookup from the read service.

* ``mart.run_artifact_v1`` — passthrough of ``meta.run_artifact`` with
  ``job_run_id_lower`` / ``run_artifact_id_lower`` shadow columns.

The builder is defensive against missing upstream tables: on a fresh DB
without any ``meta.job_run`` rows the projections are empty (zero rows),
not an exception. Re-running the builder is idempotent because each
projection uses ``CREATE OR REPLACE TABLE``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.mart._registry import register_mart_builder
from new_nfl.settings import Settings

MART_RUN_OVERVIEW_V1 = "mart.run_overview_v1"
MART_RUN_EVENT_V1 = "mart.run_event_v1"
MART_RUN_ARTIFACT_V1 = "mart.run_artifact_v1"

_SOURCE_JOB_RUN = "meta.job_run"
_SOURCE_JOB_DEF = "meta.job_definition"
_SOURCE_RUN_EVENT = "meta.run_event"
_SOURCE_RUN_ARTIFACT = "meta.run_artifact"


@dataclass(frozen=True)
class MartRunEvidenceResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    event_row_count: int
    artifact_row_count: int
    built_at: datetime


def _table_exists(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return False
    return True


def _ensure_metadata_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create minimal stubs so the builder runs on a fresh DB."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.job_definition (
            job_id VARCHAR,
            job_key VARCHAR,
            job_type VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.job_run (
            job_run_id VARCHAR,
            job_id VARCHAR,
            queue_item_id VARCHAR,
            run_status VARCHAR,
            attempt_number INTEGER,
            worker_id VARCHAR,
            message VARCHAR,
            detail_json VARCHAR,
            started_at TIMESTAMP,
            finished_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.run_event (
            run_event_id VARCHAR,
            job_run_id VARCHAR,
            event_kind VARCHAR,
            severity VARCHAR,
            message VARCHAR,
            detail_json VARCHAR,
            recorded_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.run_artifact (
            run_artifact_id VARCHAR,
            job_run_id VARCHAR,
            artifact_kind VARCHAR,
            ref_id VARCHAR,
            ref_path VARCHAR,
            detail_json VARCHAR,
            recorded_at TIMESTAMP
        )
        """
    )


@register_mart_builder("run_evidence_v1")
def build_run_evidence_v1(settings: Settings) -> MartRunEvidenceResult:
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        _ensure_metadata_tables(con)

        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_JOB_RUN}").fetchone()[0]
        )

        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_RUN_OVERVIEW_V1} AS
            WITH event_agg AS (
                SELECT
                    job_run_id,
                    COUNT(*) AS event_count,
                    SUM(CASE
                        WHEN LOWER(COALESCE(severity, '')) IN ('error', 'critical', 'fatal')
                        THEN 1 ELSE 0
                    END) AS error_event_count,
                    SUM(CASE
                        WHEN LOWER(COALESCE(severity, '')) = 'warn'
                          OR LOWER(COALESCE(severity, '')) = 'warning'
                        THEN 1 ELSE 0
                    END) AS warn_event_count,
                    MAX(recorded_at) AS last_event_recorded_at
                FROM {_SOURCE_RUN_EVENT}
                GROUP BY job_run_id
            ),
            artifact_agg AS (
                SELECT
                    job_run_id,
                    COUNT(*) AS artifact_count
                FROM {_SOURCE_RUN_ARTIFACT}
                GROUP BY job_run_id
            )
            SELECT
                r.job_run_id,
                LOWER(r.job_run_id) AS job_run_id_lower,
                r.job_id,
                d.job_key,
                LOWER(d.job_key) AS job_key_lower,
                d.job_type,
                r.queue_item_id,
                r.run_status,
                LOWER(r.run_status) AS run_status_lower,
                r.attempt_number,
                r.worker_id,
                r.message,
                r.started_at,
                r.finished_at,
                CASE
                    WHEN r.finished_at IS NOT NULL AND r.started_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (r.finished_at - r.started_at))
                END AS duration_seconds,
                COALESCE(e.event_count, 0) AS event_count,
                COALESCE(e.error_event_count, 0) AS error_event_count,
                COALESCE(e.warn_event_count, 0) AS warn_event_count,
                e.last_event_recorded_at,
                COALESCE(a.artifact_count, 0) AS artifact_count,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_JOB_RUN} r
            LEFT JOIN {_SOURCE_JOB_DEF} d ON d.job_id = r.job_id
            LEFT JOIN event_agg e ON e.job_run_id = r.job_run_id
            LEFT JOIN artifact_agg a ON a.job_run_id = r.job_run_id
            """
        )

        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_RUN_EVENT_V1} AS
            SELECT
                run_event_id,
                LOWER(run_event_id) AS run_event_id_lower,
                job_run_id,
                LOWER(job_run_id) AS job_run_id_lower,
                event_kind,
                severity,
                message,
                detail_json,
                recorded_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_RUN_EVENT}
            """
        )

        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_RUN_ARTIFACT_V1} AS
            SELECT
                run_artifact_id,
                LOWER(run_artifact_id) AS run_artifact_id_lower,
                job_run_id,
                LOWER(job_run_id) AS job_run_id_lower,
                artifact_kind,
                ref_id,
                ref_path,
                detail_json,
                recorded_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_RUN_ARTIFACT}
            """
        )

        row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {MART_RUN_OVERVIEW_V1}").fetchone()[0]
        )
        event_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {MART_RUN_EVENT_V1}").fetchone()[0]
        )
        artifact_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {MART_RUN_ARTIFACT_V1}").fetchone()[0]
        )
    finally:
        con.close()

    return MartRunEvidenceResult(
        qualified_table=MART_RUN_OVERVIEW_V1,
        source_table=_SOURCE_JOB_RUN,
        source_row_count=source_row_count,
        row_count=row_count,
        event_row_count=event_row_count,
        artifact_row_count=artifact_row_count,
        built_at=datetime.now(),
    )


__all__ = [
    "MART_RUN_ARTIFACT_V1",
    "MART_RUN_EVENT_V1",
    "MART_RUN_OVERVIEW_V1",
    "MartRunEvidenceResult",
    "build_run_evidence_v1",
]
