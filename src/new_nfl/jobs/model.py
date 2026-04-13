from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from new_nfl._db import connect as _connect
from new_nfl._db import new_id as _new_id
from new_nfl._db import row_to_dict as _row_to_dict
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings

JobType = str
# Canonical built-in job types. Extension points (tests, future domain
# executors) register additional types via ``runner.register_executor``;
# validation happens at dispatch time, not at registration time, so we keep
# the Pydantic field open.
BUILTIN_JOB_TYPES: tuple[str, ...] = (
    "fetch_remote",
    "stage_load",
    "core_load",
    "dedupe",
    "maintenance",
    "custom",
)

ScheduleKind = Literal["cron", "interval", "manual"]
BackoffKind = Literal["fixed", "exponential", "linear"]
ClaimStatus = Literal["pending", "claimed", "done", "abandoned"]
RunStatus = Literal[
    "pending",
    "running",
    "success",
    "failed",
    "retrying",
    "quarantined",
]


class RetryPolicy(BaseModel):
    retry_policy_id: str
    policy_key: str
    max_attempts: int = Field(ge=1)
    backoff_kind: BackoffKind
    base_seconds: int = Field(ge=0)
    max_seconds: int | None = None
    jitter_ratio: float | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobDefinition(BaseModel):
    job_id: str
    job_key: str
    job_type: JobType
    target_ref: str | None = None
    description: str | None = None
    is_active: bool = True
    concurrency_key: str | None = None
    params_json: str = "{}"
    retry_policy_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("params_json")
    @classmethod
    def _params_is_json(cls, value: str) -> str:
        json.loads(value)
        return value


class JobSchedule(BaseModel):
    schedule_id: str
    job_id: str
    schedule_kind: ScheduleKind
    schedule_expr: str | None = None
    timezone: str | None = None
    is_active: bool = True
    next_fire_at: datetime | None = None
    last_fired_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobQueueItem(BaseModel):
    queue_item_id: str
    job_id: str
    idempotency_key: str | None = None
    priority: int = 100
    trigger_kind: str = "manual"
    claim_status: ClaimStatus = "pending"
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    attempt_count: int = 0
    params_json: str = "{}"
    scheduled_for: datetime | None = None
    enqueued_at: datetime | None = None


class JobRun(BaseModel):
    job_run_id: str
    job_id: str
    queue_item_id: str | None = None
    run_status: RunStatus
    attempt_number: int = 1
    worker_id: str | None = None
    message: str | None = None
    detail_json: str = "{}"
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunEvent(BaseModel):
    run_event_id: str
    job_run_id: str
    event_kind: str
    severity: str | None = None
    message: str | None = None
    detail_json: str = "{}"
    recorded_at: datetime | None = None


class RunArtifact(BaseModel):
    run_artifact_id: str
    job_run_id: str
    artifact_kind: str
    ref_id: str | None = None
    ref_path: str | None = None
    detail_json: str = "{}"
    recorded_at: datetime | None = None


def register_retry_policy(
    settings: Settings,
    *,
    policy_key: str,
    max_attempts: int,
    backoff_kind: BackoffKind,
    base_seconds: int,
    max_seconds: int | None = None,
    jitter_ratio: float | None = None,
    notes: str | None = None,
) -> RetryPolicy:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        existing = _row_to_dict(
            con,
            "SELECT * FROM meta.retry_policy WHERE policy_key = ?",
            [policy_key],
        )
        if existing:
            retry_policy_id = existing[0]["retry_policy_id"]
            con.execute(
                """
                UPDATE meta.retry_policy
                SET max_attempts = ?,
                    backoff_kind = ?,
                    base_seconds = ?,
                    max_seconds = ?,
                    jitter_ratio = ?,
                    notes = ?,
                    updated_at = current_timestamp
                WHERE retry_policy_id = ?
                """,
                [
                    max_attempts,
                    backoff_kind,
                    base_seconds,
                    max_seconds,
                    jitter_ratio,
                    notes,
                    retry_policy_id,
                ],
            )
        else:
            retry_policy_id = _new_id()
            con.execute(
                """
                INSERT INTO meta.retry_policy
                    (retry_policy_id, policy_key, max_attempts, backoff_kind,
                     base_seconds, max_seconds, jitter_ratio, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    retry_policy_id,
                    policy_key,
                    max_attempts,
                    backoff_kind,
                    base_seconds,
                    max_seconds,
                    jitter_ratio,
                    notes,
                ],
            )
        row = _row_to_dict(
            con,
            "SELECT * FROM meta.retry_policy WHERE retry_policy_id = ?",
            [retry_policy_id],
        )[0]
        return RetryPolicy.model_validate(row)
    finally:
        con.close()


def register_job(
    settings: Settings,
    *,
    job_key: str,
    job_type: JobType,
    target_ref: str | None = None,
    description: str | None = None,
    is_active: bool = True,
    concurrency_key: str | None = None,
    params: dict[str, Any] | None = None,
    retry_policy_key: str | None = None,
) -> JobDefinition:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        retry_policy_id: str | None = None
        if retry_policy_key is not None:
            match = _row_to_dict(
                con,
                "SELECT retry_policy_id FROM meta.retry_policy WHERE policy_key = ?",
                [retry_policy_key],
            )
            if not match:
                raise ValueError(
                    f"retry_policy_key '{retry_policy_key}' not registered"
                )
            retry_policy_id = match[0]["retry_policy_id"]

        params_json = json.dumps(params or {}, sort_keys=True, ensure_ascii=False)

        existing = _row_to_dict(
            con,
            "SELECT job_id FROM meta.job_definition WHERE job_key = ?",
            [job_key],
        )
        if existing:
            job_id = existing[0]["job_id"]
            con.execute(
                """
                UPDATE meta.job_definition
                SET job_type = ?,
                    target_ref = ?,
                    description = ?,
                    is_active = ?,
                    concurrency_key = ?,
                    params_json = ?,
                    retry_policy_id = ?,
                    updated_at = current_timestamp
                WHERE job_id = ?
                """,
                [
                    job_type,
                    target_ref,
                    description,
                    is_active,
                    concurrency_key,
                    params_json,
                    retry_policy_id,
                    job_id,
                ],
            )
        else:
            job_id = _new_id()
            con.execute(
                """
                INSERT INTO meta.job_definition
                    (job_id, job_key, job_type, target_ref, description,
                     is_active, concurrency_key, params_json, retry_policy_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    job_id,
                    job_key,
                    job_type,
                    target_ref,
                    description,
                    is_active,
                    concurrency_key,
                    params_json,
                    retry_policy_id,
                ],
            )
        row = _row_to_dict(
            con,
            "SELECT * FROM meta.job_definition WHERE job_id = ?",
            [job_id],
        )[0]
        return JobDefinition.model_validate(row)
    finally:
        con.close()


def upsert_schedule(
    settings: Settings,
    *,
    job_key: str,
    schedule_kind: ScheduleKind,
    schedule_expr: str | None = None,
    timezone: str | None = None,
    is_active: bool = True,
) -> JobSchedule:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        job_row = _row_to_dict(
            con,
            "SELECT job_id FROM meta.job_definition WHERE job_key = ?",
            [job_key],
        )
        if not job_row:
            raise ValueError(f"job_key '{job_key}' not registered")
        job_id = job_row[0]["job_id"]

        existing = _row_to_dict(
            con,
            """
            SELECT schedule_id FROM meta.job_schedule
            WHERE job_id = ? AND schedule_kind = ?
              AND COALESCE(schedule_expr, '') = COALESCE(?, '')
            """,
            [job_id, schedule_kind, schedule_expr],
        )
        if existing:
            schedule_id = existing[0]["schedule_id"]
            con.execute(
                """
                UPDATE meta.job_schedule
                SET timezone = ?, is_active = ?, updated_at = current_timestamp
                WHERE schedule_id = ?
                """,
                [timezone, is_active, schedule_id],
            )
        else:
            schedule_id = _new_id()
            con.execute(
                """
                INSERT INTO meta.job_schedule
                    (schedule_id, job_id, schedule_kind, schedule_expr,
                     timezone, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    schedule_id,
                    job_id,
                    schedule_kind,
                    schedule_expr,
                    timezone,
                    is_active,
                ],
            )
        row = _row_to_dict(
            con,
            "SELECT * FROM meta.job_schedule WHERE schedule_id = ?",
            [schedule_id],
        )[0]
        return JobSchedule.model_validate(row)
    finally:
        con.close()


def enqueue_job(
    settings: Settings,
    *,
    job_key: str,
    trigger_kind: str = "manual",
    idempotency_key: str | None = None,
    priority: int = 100,
    params: dict[str, Any] | None = None,
    scheduled_for: datetime | None = None,
) -> JobQueueItem:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        job_row = _row_to_dict(
            con,
            "SELECT job_id FROM meta.job_definition WHERE job_key = ?",
            [job_key],
        )
        if not job_row:
            raise ValueError(f"job_key '{job_key}' not registered")
        job_id = job_row[0]["job_id"]

        if idempotency_key is not None:
            pending = _row_to_dict(
                con,
                """
                SELECT queue_item_id FROM meta.job_queue
                WHERE job_id = ? AND idempotency_key = ?
                  AND claim_status IN ('pending', 'claimed')
                """,
                [job_id, idempotency_key],
            )
            if pending:
                row = _row_to_dict(
                    con,
                    "SELECT * FROM meta.job_queue WHERE queue_item_id = ?",
                    [pending[0]["queue_item_id"]],
                )[0]
                return JobQueueItem.model_validate(row)

        queue_item_id = _new_id()
        params_json = json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
        con.execute(
            """
            INSERT INTO meta.job_queue
                (queue_item_id, job_id, idempotency_key, priority,
                 trigger_kind, claim_status, attempt_count, params_json,
                 scheduled_for)
            VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?)
            """,
            [
                queue_item_id,
                job_id,
                idempotency_key,
                priority,
                trigger_kind,
                params_json,
                scheduled_for,
            ],
        )
        row = _row_to_dict(
            con,
            "SELECT * FROM meta.job_queue WHERE queue_item_id = ?",
            [queue_item_id],
        )[0]
        return JobQueueItem.model_validate(row)
    finally:
        con.close()


def list_jobs(settings: Settings) -> list[JobDefinition]:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        rows = _row_to_dict(
            con,
            """
            SELECT *
            FROM meta.job_definition
            ORDER BY job_key
            """,
        )
        return [JobDefinition.model_validate(row) for row in rows]
    finally:
        con.close()


def describe_job(settings: Settings, job_key: str) -> dict[str, Any] | None:
    ensure_metadata_surface(settings)
    con = _connect(settings)
    try:
        job_rows = _row_to_dict(
            con,
            "SELECT * FROM meta.job_definition WHERE job_key = ?",
            [job_key],
        )
        if not job_rows:
            return None
        job = JobDefinition.model_validate(job_rows[0])

        retry_policy: RetryPolicy | None = None
        if job.retry_policy_id is not None:
            pol_rows = _row_to_dict(
                con,
                "SELECT * FROM meta.retry_policy WHERE retry_policy_id = ?",
                [job.retry_policy_id],
            )
            if pol_rows:
                retry_policy = RetryPolicy.model_validate(pol_rows[0])

        schedule_rows = _row_to_dict(
            con,
            """
            SELECT * FROM meta.job_schedule
            WHERE job_id = ?
            ORDER BY schedule_kind, schedule_expr
            """,
            [job.job_id],
        )
        schedules = [JobSchedule.model_validate(row) for row in schedule_rows]

        recent_run_rows = _row_to_dict(
            con,
            """
            SELECT * FROM meta.job_run
            WHERE job_id = ?
            ORDER BY started_at DESC
            LIMIT 5
            """,
            [job.job_id],
        )
        recent_runs = [JobRun.model_validate(row) for row in recent_run_rows]

        return {
            "job": job,
            "retry_policy": retry_policy,
            "schedules": schedules,
            "recent_runs": recent_runs,
        }
    finally:
        con.close()
