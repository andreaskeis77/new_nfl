"""Internal job runner (T2.3B).

Implements the worker loop that claims pending items from ``meta.job_queue``
atomically, dispatches to an executor based on ``job_type``, writes the run
evidence into ``meta.job_run`` / ``meta.run_event`` / ``meta.run_artifact``
and drives retry scheduling through ``meta.retry_policy``.

Design anchors: ADR-0025 (internal job and run model) and Engineering
Manifest v1.3 §3.9 (Replay-Pflicht) / §3.13 (Autonomie mit Sichtbarkeit).
"""
from __future__ import annotations

import json
import socket
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from new_nfl._db import connect, new_id, row_to_dict
from new_nfl.jobs.model import (
    JobQueueItem,
    JobRun,
    RetryPolicy,
)
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings

# ---------------------------------------------------------------------------
# Executor contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionArtifact:
    artifact_kind: str
    ref_id: str | None = None
    ref_path: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    success: bool
    message: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ExecutionArtifact] = field(default_factory=list)


Executor = Callable[[Settings, dict[str, Any]], ExecutionResult]


# ---------------------------------------------------------------------------
# Default executors
# ---------------------------------------------------------------------------


def _executor_fetch_remote(settings: Settings, params: dict[str, Any]) -> ExecutionResult:
    from new_nfl.adapters import execute_remote_fetch
    from new_nfl.adapters.slices import DEFAULT_SLICE_KEY

    adapter_id = params["adapter_id"]
    execute_flag = bool(params.get("execute", True))
    remote_url = params.get("remote_url") or None
    slice_key = params.get("slice_key") or DEFAULT_SLICE_KEY

    result = execute_remote_fetch(
        settings,
        adapter_id=adapter_id,
        execute=execute_flag,
        remote_url_override=remote_url,
        slice_key=slice_key,
    )
    detail = {
        "adapter_id": result.adapter_id,
        "pipeline_name": result.pipeline_name,
        "run_mode": result.run_mode,
        "run_status": result.run_status,
        "ingest_run_id": result.ingest_run_id,
        "landing_dir": result.landing_dir,
        "manifest_path": result.manifest_path,
        "receipt_path": result.receipt_path,
        "load_event_id": result.load_event_id,
        "landed_file_count": result.landed_file_count,
        "asset_count": result.asset_count,
        "stage_dataset": result.stage_dataset,
        "source_status": result.source_status,
        "source_url": result.source_url,
        "downloaded_file_path": result.downloaded_file_path,
        "downloaded_bytes": result.downloaded_bytes,
        "sha256_hex": result.sha256_hex,
    }
    artifacts: list[ExecutionArtifact] = []
    if result.ingest_run_id:
        artifacts.append(
            ExecutionArtifact(
                artifact_kind="ingest_run",
                ref_id=result.ingest_run_id,
                detail={"pipeline_name": result.pipeline_name},
            )
        )
    if result.downloaded_file_path:
        artifacts.append(
            ExecutionArtifact(
                artifact_kind="source_file",
                ref_path=result.downloaded_file_path,
                detail={"sha256_hex": result.sha256_hex},
            )
        )
    return ExecutionResult(
        success=True,
        message=f"remote_fetch adapter_id={adapter_id} run_status={result.run_status}",
        detail=detail,
        artifacts=artifacts,
    )


def _executor_stage_load(settings: Settings, params: dict[str, Any]) -> ExecutionResult:
    from new_nfl.adapters.slices import DEFAULT_SLICE_KEY
    from new_nfl.stage_load import execute_stage_load

    adapter_id = params["adapter_id"]
    execute_flag = bool(params.get("execute", True))
    source_file_id = params.get("source_file_id") or None
    slice_key = params.get("slice_key") or DEFAULT_SLICE_KEY

    result = execute_stage_load(
        settings,
        adapter_id=adapter_id,
        execute=execute_flag,
        source_file_id=source_file_id,
        slice_key=slice_key,
    )
    detail = {
        "adapter_id": result.adapter_id,
        "pipeline_name": result.pipeline_name,
        "run_mode": result.run_mode,
        "run_status": result.run_status,
        "ingest_run_id": result.ingest_run_id,
        "source_file_id": result.source_file_id,
        "source_file_path": result.source_file_path,
        "target_schema": result.target_schema,
        "target_object": result.target_object,
        "qualified_table": result.qualified_table,
        "row_count": result.row_count,
        "load_event_id": result.load_event_id,
        "stage_dataset": result.stage_dataset,
        "source_status": result.source_status,
    }
    artifacts = [
        ExecutionArtifact(
            artifact_kind="ingest_run",
            ref_id=result.ingest_run_id,
            detail={"pipeline_name": result.pipeline_name},
        ),
        ExecutionArtifact(
            artifact_kind="stage_table",
            ref_id=result.qualified_table,
            detail={"row_count": result.row_count},
        ),
    ]
    return ExecutionResult(
        success=True,
        message=f"stage_load adapter_id={adapter_id} rows={result.row_count}",
        detail=detail,
        artifacts=artifacts,
    )


def _executor_custom(settings: Settings, params: dict[str, Any]) -> ExecutionResult:
    """Deterministic no-op executor used by tests and as a maintenance stub.

    Emits one artifact of kind ``custom_output`` whose ``ref_id`` is
    deterministic in the input params — this lets replay tests assert that
    two runs against the same input produce identical artifacts.
    """
    import hashlib

    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return ExecutionResult(
        success=True,
        message=f"custom digest={digest}",
        detail={"digest": digest, "params_echo": params},
        artifacts=[
            ExecutionArtifact(
                artifact_kind="custom_output",
                ref_id=digest,
                detail={"params": params},
            )
        ],
    )


def _executor_mart_build(settings: Settings, params: dict[str, Any]) -> ExecutionResult:
    """Rebuild a versioned ``mart.*`` read projection (ADR-0029).

    ``params['mart_key']`` selects the projection. Each projection is a full
    rebuild (``CREATE OR REPLACE TABLE``) over ``core.*``; the runner records
    the build as a ``meta.job_run`` so operators can audit freshness.
    """
    from new_nfl.mart import (
        build_game_overview_v1,
        build_player_overview_v1,
        build_roster_current_v1,
        build_roster_history_v1,
        build_schedule_field_dictionary_v1,
        build_team_overview_v1,
        build_team_stats_season_v1,
        build_team_stats_weekly_v1,
    )

    mart_key = params.get("mart_key", "schedule_field_dictionary_v1")
    if mart_key == "schedule_field_dictionary_v1":
        result = build_schedule_field_dictionary_v1(settings)
    elif mart_key == "team_overview_v1":
        result = build_team_overview_v1(settings)
    elif mart_key == "game_overview_v1":
        result = build_game_overview_v1(settings)
    elif mart_key == "player_overview_v1":
        result = build_player_overview_v1(settings)
    elif mart_key == "roster_current_v1":
        result = build_roster_current_v1(settings)
    elif mart_key == "roster_history_v1":
        result = build_roster_history_v1(settings)
    elif mart_key == "team_stats_weekly_v1":
        result = build_team_stats_weekly_v1(settings)
    elif mart_key == "team_stats_season_v1":
        result = build_team_stats_season_v1(settings)
    else:
        raise ValueError(f"unknown mart_key={mart_key!r}")

    return ExecutionResult(
        success=True,
        message=(
            f"mart_build mart_key={mart_key} "
            f"rows={result.row_count} source_rows={result.source_row_count}"
        ),
        detail={
            "mart_key": mart_key,
            "qualified_table": result.qualified_table,
            "source_table": result.source_table,
            "source_row_count": result.source_row_count,
            "row_count": result.row_count,
            "built_at": result.built_at.isoformat() if result.built_at else None,
        },
        artifacts=[
            ExecutionArtifact(
                artifact_kind="mart_table",
                ref_id=result.qualified_table,
                detail={"row_count": result.row_count},
            )
        ],
    )


EXECUTORS: dict[str, Executor] = {
    "fetch_remote": _executor_fetch_remote,
    "stage_load": _executor_stage_load,
    "mart_build": _executor_mart_build,
    "custom": _executor_custom,
}


def register_executor(job_type: str, executor: Executor) -> None:
    """Register or override an executor for a ``job_type`` (used by tests)."""
    EXECUTORS[job_type] = executor


# ---------------------------------------------------------------------------
# Runner summary types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunnerTick:
    """Outcome of a single worker tick."""

    claimed: bool
    job_run_id: str | None
    job_key: str | None
    job_type: str | None
    run_status: str | None
    message: str | None
    detail: dict[str, Any]

    @classmethod
    def idle(cls) -> "RunnerTick":
        return cls(
            claimed=False,
            job_run_id=None,
            job_key=None,
            job_type=None,
            run_status=None,
            message=None,
            detail={},
        )


# ---------------------------------------------------------------------------
# Worker identity
# ---------------------------------------------------------------------------


def default_worker_id() -> str:
    host = socket.gethostname() or "worker"
    return f"{host}:{new_id()[:8]}"


# ---------------------------------------------------------------------------
# Backoff math
# ---------------------------------------------------------------------------


def compute_backoff_seconds(policy: RetryPolicy, attempt_number: int) -> int:
    """Return the backoff delay before ``attempt_number + 1``.

    ``attempt_number`` is the count that has already been attempted. Linear
    and exponential policies scale off the base; ``max_seconds`` caps the
    delay. Jitter is intentionally not applied here to keep unit tests
    deterministic; the hook stays in the policy shape for a later refinement.
    """
    kind = policy.backoff_kind
    base = max(policy.base_seconds, 0)
    if kind == "fixed":
        delay = base
    elif kind == "linear":
        delay = base * max(attempt_number, 1)
    elif kind == "exponential":
        delay = base * (2 ** max(attempt_number - 1, 0))
    else:
        delay = base
    if policy.max_seconds is not None:
        delay = min(delay, policy.max_seconds)
    return int(delay)


# ---------------------------------------------------------------------------
# Core SQL helpers
# ---------------------------------------------------------------------------


_CLAIM_CANDIDATE_SQL = """
SELECT q.queue_item_id, q.job_id, q.attempt_count, q.params_json,
       q.idempotency_key, q.trigger_kind, q.priority,
       d.job_key, d.job_type, d.target_ref, d.concurrency_key,
       d.retry_policy_id, d.params_json AS def_params_json
FROM meta.job_queue q
JOIN meta.job_definition d ON d.job_id = q.job_id
WHERE q.claim_status = 'pending'
  AND (q.scheduled_for IS NULL OR q.scheduled_for <= current_timestamp)
  AND (
    d.concurrency_key IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM meta.job_queue q2
      JOIN meta.job_definition d2 ON d2.job_id = q2.job_id
      WHERE q2.claim_status = 'claimed'
        AND d2.concurrency_key = d.concurrency_key
    )
  )
ORDER BY q.priority ASC, q.enqueued_at ASC
LIMIT 1
"""


_CLAIM_UPDATE_SQL = """
UPDATE meta.job_queue
SET claim_status = 'claimed',
    claimed_by = ?,
    claimed_at = current_timestamp,
    attempt_count = attempt_count + 1
WHERE queue_item_id = ?
  AND claim_status = 'pending'
RETURNING queue_item_id, job_id, attempt_count, params_json,
          idempotency_key, trigger_kind, priority,
          claim_status, claimed_by, claimed_at,
          scheduled_for, enqueued_at
"""


def _claim_one(
    con: Any,
    worker_id: str,
    *,
    queue_item_id: str | None = None,
) -> dict[str, Any] | None:
    """Atomically move one pending item to ``claimed``.

    When ``queue_item_id`` is given the claim is restricted to that specific
    item — used by the CLI-sync path. Concurrency-key blocking still applies.
    Returns the merged queue + definition row or ``None`` if no candidate
    could be claimed.
    """
    con.begin()
    try:
        if queue_item_id is None:
            rows = row_to_dict(con, _CLAIM_CANDIDATE_SQL)
            if not rows:
                con.commit()
                return None
            candidate = rows[0]
        else:
            sql = _CLAIM_CANDIDATE_SQL.replace(
                "WHERE q.claim_status = 'pending'",
                "WHERE q.claim_status = 'pending' AND q.queue_item_id = ?",
            )
            rows = row_to_dict(con, sql, [queue_item_id])
            if not rows:
                con.commit()
                return None
            candidate = rows[0]

        updated = row_to_dict(
            con, _CLAIM_UPDATE_SQL, [worker_id, candidate["queue_item_id"]]
        )
        if not updated:
            con.commit()
            return None
        # merge the updated queue row back into the candidate (for fresh
        # attempt_count and claimed_at)
        candidate.update(updated[0])
        con.commit()
        return candidate
    except Exception:
        con.rollback()
        raise


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------


def _insert_run_event(
    con: Any,
    *,
    job_run_id: str,
    event_kind: str,
    severity: str | None = None,
    message: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO meta.run_event
            (run_event_id, job_run_id, event_kind, severity, message, detail_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            new_id(),
            job_run_id,
            event_kind,
            severity,
            message,
            json.dumps(detail or {}, sort_keys=True, ensure_ascii=False),
        ],
    )


def _insert_run_artifact(
    con: Any,
    *,
    job_run_id: str,
    artifact: ExecutionArtifact,
) -> None:
    con.execute(
        """
        INSERT INTO meta.run_artifact
            (run_artifact_id, job_run_id, artifact_kind, ref_id, ref_path, detail_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            new_id(),
            job_run_id,
            artifact.artifact_kind,
            artifact.ref_id,
            artifact.ref_path,
            json.dumps(artifact.detail, sort_keys=True, ensure_ascii=False),
        ],
    )


def _load_retry_policy(con: Any, retry_policy_id: str | None) -> RetryPolicy | None:
    if retry_policy_id is None:
        return None
    rows = row_to_dict(
        con,
        "SELECT * FROM meta.retry_policy WHERE retry_policy_id = ?",
        [retry_policy_id],
    )
    if not rows:
        return None
    return RetryPolicy.model_validate(rows[0])


def _finalize_success(
    con: Any,
    *,
    job_run_id: str,
    queue_item_id: str,
    result: ExecutionResult,
) -> None:
    con.execute(
        """
        UPDATE meta.job_run
        SET run_status = 'success',
            message = ?,
            detail_json = ?,
            finished_at = current_timestamp
        WHERE job_run_id = ?
        """,
        [
            result.message,
            json.dumps(result.detail, sort_keys=True, ensure_ascii=False),
            job_run_id,
        ],
    )
    con.execute(
        """
        UPDATE meta.job_queue
        SET claim_status = 'done'
        WHERE queue_item_id = ?
        """,
        [queue_item_id],
    )


def _finalize_failure(
    con: Any,
    *,
    job_run_id: str,
    queue_item_id: str,
    attempt_number: int,
    policy: RetryPolicy | None,
    message: str,
    detail: dict[str, Any],
) -> str:
    """Close a failed attempt, schedule a retry if policy allows.

    Returns the final ``run_status`` written to ``meta.job_run`` —
    ``'retrying'`` when another attempt is queued, otherwise ``'failed'``.
    """
    max_attempts = policy.max_attempts if policy is not None else 1
    if attempt_number < max_attempts:
        backoff = (
            compute_backoff_seconds(policy, attempt_number) if policy else 0
        )
        con.execute(
            """
            UPDATE meta.job_queue
            SET claim_status = 'pending',
                claimed_by = NULL,
                claimed_at = NULL,
                scheduled_for = current_timestamp + (? * INTERVAL 1 SECOND)
            WHERE queue_item_id = ?
            """,
            [backoff, queue_item_id],
        )
        con.execute(
            """
            UPDATE meta.job_run
            SET run_status = 'retrying',
                message = ?,
                detail_json = ?,
                finished_at = current_timestamp
            WHERE job_run_id = ?
            """,
            [
                message,
                json.dumps(
                    {**detail, "retry_backoff_seconds": backoff},
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                job_run_id,
            ],
        )
        _insert_run_event(
            con,
            job_run_id=job_run_id,
            event_kind="retry_scheduled",
            severity="warning",
            message=f"attempt {attempt_number}/{max_attempts} failed; "
            f"backoff={backoff}s",
            detail={"attempt_number": attempt_number, "backoff_seconds": backoff},
        )
        return "retrying"

    con.execute(
        """
        UPDATE meta.job_queue
        SET claim_status = 'abandoned'
        WHERE queue_item_id = ?
        """,
        [queue_item_id],
    )
    con.execute(
        """
        UPDATE meta.job_run
        SET run_status = 'failed',
            message = ?,
            detail_json = ?,
            finished_at = current_timestamp
        WHERE job_run_id = ?
        """,
        [
            message,
            json.dumps(detail, sort_keys=True, ensure_ascii=False),
            job_run_id,
        ],
    )
    _insert_run_event(
        con,
        job_run_id=job_run_id,
        event_kind="retry_exhausted",
        severity="error",
        message=f"attempt {attempt_number}/{max_attempts} failed; no more retries",
        detail={"attempt_number": attempt_number},
    )
    return "failed"


def _auto_quarantine_failed_run(
    settings: Settings,
    *,
    job_run_id: str,
    job_key: str,
    job_type: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    """Open (or refresh) a quarantine case for a runner-exhausted failure.

    Manifest §3.12 (Quarantäne ist ein Lebenszustand) — a failed run cannot
    be silently abandoned. The case is keyed by ``(job_run, job_run_id,
    runner_exhausted)`` so each failed run gets exactly one case.
    """
    # Local import keeps the module dependency one-way (quarantine -> runner
    # for replay; runner -> quarantine only at call time).
    from new_nfl.jobs.quarantine import open_quarantine_case

    open_quarantine_case(
        settings,
        scope_type="job_run",
        scope_ref=job_run_id,
        reason_code="runner_exhausted",
        severity="error",
        evidence_refs=[
            {
                "kind": "job_run",
                "job_run_id": job_run_id,
                "job_key": job_key,
                "job_type": job_type,
            }
        ],
        notes=message,
    )


def _execute_claimed(
    settings: Settings,
    claimed: dict[str, Any],
    worker_id: str,
) -> RunnerTick:
    queue_item_id: str = claimed["queue_item_id"]
    job_id: str = claimed["job_id"]
    job_key: str = claimed["job_key"]
    job_type: str = claimed["job_type"]
    attempt_number: int = int(claimed["attempt_count"])
    queue_params = json.loads(claimed.get("params_json") or "{}")
    def_params = json.loads(claimed.get("def_params_json") or "{}")
    effective_params: dict[str, Any] = {**def_params, **queue_params}
    if claimed.get("target_ref") and "adapter_id" not in effective_params:
        # `fetch_remote` / `stage_load` need an adapter_id; use target_ref as default
        effective_params["adapter_id"] = claimed["target_ref"]

    executor = EXECUTORS.get(job_type)
    job_run_id = new_id()

    con = connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.job_run
                (job_run_id, job_id, queue_item_id, run_status, attempt_number,
                 worker_id, message, detail_json)
            VALUES (?, ?, ?, 'running', ?, ?, NULL, '{}')
            """,
            [job_run_id, job_id, queue_item_id, attempt_number, worker_id],
        )
        _insert_run_event(
            con,
            job_run_id=job_run_id,
            event_kind="run_started",
            severity="info",
            message=f"job_key={job_key} attempt={attempt_number}",
            detail={
                "job_key": job_key,
                "job_type": job_type,
                "attempt_number": attempt_number,
                "worker_id": worker_id,
            },
        )

        if executor is None:
            policy = _load_retry_policy(con, claimed.get("retry_policy_id"))
            message = f"no executor registered for job_type={job_type}"
            final_status = _finalize_failure(
                con,
                job_run_id=job_run_id,
                queue_item_id=queue_item_id,
                attempt_number=attempt_number,
                policy=policy,
                message=message,
                detail={"job_type": job_type},
            )
            no_executor_status = final_status
    finally:
        con.close()
    if executor is None:
        if no_executor_status == "failed":
            _auto_quarantine_failed_run(
                settings,
                job_run_id=job_run_id,
                job_key=job_key,
                job_type=job_type,
                message=f"no executor registered for job_type={job_type}",
                detail={"job_type": job_type},
            )
        return RunnerTick(
            claimed=True,
            job_run_id=job_run_id,
            job_key=job_key,
            job_type=job_type,
            run_status=no_executor_status,
            message=f"no executor registered for job_type={job_type}",
            detail={},
        )

    try:
        result = executor(settings, effective_params)
    except Exception as exc:  # executor raised
        tb = traceback.format_exc()
        con = connect(settings)
        try:
            policy = _load_retry_policy(con, claimed.get("retry_policy_id"))
            final_status = _finalize_failure(
                con,
                job_run_id=job_run_id,
                queue_item_id=queue_item_id,
                attempt_number=attempt_number,
                policy=policy,
                message=f"executor raised: {exc}",
                detail={"error": str(exc), "traceback": tb},
            )
            _insert_run_event(
                con,
                job_run_id=job_run_id,
                event_kind="run_failed",
                severity="error",
                message=str(exc),
                detail={"traceback": tb},
            )
        finally:
            con.close()
        if final_status == "failed":
            _auto_quarantine_failed_run(
                settings,
                job_run_id=job_run_id,
                job_key=job_key,
                job_type=job_type,
                message=f"executor raised: {exc}",
                detail={"error": str(exc)},
            )
        return RunnerTick(
            claimed=True,
            job_run_id=job_run_id,
            job_key=job_key,
            job_type=job_type,
            run_status=final_status,
            message=f"executor raised: {exc}",
            detail={"error": str(exc)},
        )

    con = connect(settings)
    try:
        if result.success:
            _finalize_success(
                con,
                job_run_id=job_run_id,
                queue_item_id=queue_item_id,
                result=result,
            )
            for artifact in result.artifacts:
                _insert_run_artifact(con, job_run_id=job_run_id, artifact=artifact)
            _insert_run_event(
                con,
                job_run_id=job_run_id,
                event_kind="run_succeeded",
                severity="info",
                message=result.message,
                detail={"artifact_count": len(result.artifacts)},
            )
            final_status = "success"
        else:
            policy = _load_retry_policy(con, claimed.get("retry_policy_id"))
            final_status = _finalize_failure(
                con,
                job_run_id=job_run_id,
                queue_item_id=queue_item_id,
                attempt_number=attempt_number,
                policy=policy,
                message=result.message or "executor reported failure",
                detail=result.detail,
            )
            for artifact in result.artifacts:
                _insert_run_artifact(con, job_run_id=job_run_id, artifact=artifact)
    finally:
        con.close()

    if final_status == "failed":
        _auto_quarantine_failed_run(
            settings,
            job_run_id=job_run_id,
            job_key=job_key,
            job_type=job_type,
            message=result.message or "executor reported failure",
            detail=result.detail,
        )

    return RunnerTick(
        claimed=True,
        job_run_id=job_run_id,
        job_key=job_key,
        job_type=job_type,
        run_status=final_status,
        message=result.message,
        detail=result.detail,
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def claim_next(settings: Settings, worker_id: str) -> JobQueueItem | None:
    """Atomically claim the next eligible pending queue item.

    Exposed for tests and future diagnostics — in production flows the
    caller should use ``run_worker_once`` which also executes the claim.
    """
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        claimed = _claim_one(con, worker_id)
    finally:
        con.close()
    if claimed is None:
        return None
    # Build JobQueueItem from the canonical queue row; we stored the whole
    # merged dict in ``claimed`` but only the queue columns match the model.
    queue_cols = {
        key: claimed[key]
        for key in (
            "queue_item_id",
            "job_id",
            "idempotency_key",
            "priority",
            "trigger_kind",
            "claim_status",
            "claimed_by",
            "claimed_at",
            "attempt_count",
            "params_json",
            "scheduled_for",
            "enqueued_at",
        )
        if key in claimed
    }
    return JobQueueItem.model_validate(queue_cols)


def run_worker_once(
    settings: Settings,
    *,
    worker_id: str | None = None,
    queue_item_id: str | None = None,
) -> RunnerTick:
    """Perform one claim+execute tick.

    Returns ``RunnerTick.idle()`` when no item was eligible. When
    ``queue_item_id`` is given the claim is restricted to that specific
    queue item (used by the CLI sync path).
    """
    ensure_metadata_surface(settings)
    worker_id = worker_id or default_worker_id()
    con = connect(settings)
    try:
        claimed = _claim_one(con, worker_id, queue_item_id=queue_item_id)
    finally:
        con.close()
    if claimed is None:
        return RunnerTick.idle()
    return _execute_claimed(settings, claimed, worker_id)


def run_worker_serve(
    settings: Settings,
    *,
    worker_id: str | None = None,
    idle_sleep_seconds: float = 5.0,
    max_iterations: int | None = None,
    stop_when_idle: bool = False,
) -> list[RunnerTick]:
    """Run the worker loop continuously.

    ``max_iterations`` caps the total number of ticks executed (idle ticks
    included); ``stop_when_idle`` exits the first time the queue is empty.
    Both are primarily useful for tests and one-shot operator invocations.
    """
    ensure_metadata_surface(settings)
    worker_id = worker_id or default_worker_id()
    ticks: list[RunnerTick] = []
    iteration = 0
    while True:
        if max_iterations is not None and iteration >= max_iterations:
            break
        tick = run_worker_once(settings, worker_id=worker_id)
        ticks.append(tick)
        iteration += 1
        if not tick.claimed:
            if stop_when_idle:
                break
            time.sleep(idle_sleep_seconds)
    return ticks


def replay_failed_run(
    settings: Settings,
    *,
    job_run_id: str,
    worker_id: str | None = None,
) -> RunnerTick:
    """Replay a previously failed run by enqueueing a fresh queue item.

    Carries the original queue params forward. The replay produces a new
    ``meta.job_run`` row linked to a new ``meta.job_queue`` entry — the
    immutable evidence of the failed run is preserved.
    """
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        rows = row_to_dict(
            con,
            """
            SELECT r.job_run_id, r.job_id, r.queue_item_id, r.run_status,
                   q.params_json AS queue_params_json,
                   q.trigger_kind, q.priority
            FROM meta.job_run r
            LEFT JOIN meta.job_queue q ON q.queue_item_id = r.queue_item_id
            WHERE r.job_run_id = ?
            """,
            [job_run_id],
        )
        if not rows:
            raise ValueError(f"unknown job_run_id={job_run_id}")
        run = rows[0]
        if run["run_status"] != "failed":
            raise ValueError(
                f"job_run_id={job_run_id} is in status {run['run_status']}, not 'failed'"
            )
        params_json = run["queue_params_json"] or "{}"
        queue_item_id = new_id()
        con.execute(
            """
            INSERT INTO meta.job_queue
                (queue_item_id, job_id, idempotency_key, priority,
                 trigger_kind, claim_status, attempt_count, params_json,
                 scheduled_for)
            VALUES (?, ?, NULL, ?, 'replay', 'pending', 0, ?, NULL)
            """,
            [
                queue_item_id,
                run["job_id"],
                int(run["priority"]) if run["priority"] is not None else 100,
                params_json,
            ],
        )
        _insert_run_event(
            con,
            job_run_id=job_run_id,
            event_kind="replay_enqueued",
            severity="info",
            message=f"replay queued as queue_item_id={queue_item_id}",
            detail={"new_queue_item_id": queue_item_id},
        )
    finally:
        con.close()
    return run_worker_once(
        settings,
        worker_id=worker_id,
        queue_item_id=queue_item_id,
    )


def load_run(settings: Settings, job_run_id: str) -> JobRun | None:
    """Fetch a ``meta.job_run`` row as a Pydantic model, or ``None``."""
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        rows = row_to_dict(
            con,
            "SELECT * FROM meta.job_run WHERE job_run_id = ?",
            [job_run_id],
        )
    finally:
        con.close()
    if not rows:
        return None
    return JobRun.model_validate(rows[0])


def list_run_artifacts(settings: Settings, job_run_id: str) -> list[dict[str, Any]]:
    """Return artifact rows for a run as plain dicts."""
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        return row_to_dict(
            con,
            """
            SELECT * FROM meta.run_artifact
            WHERE job_run_id = ?
            ORDER BY recorded_at, run_artifact_id
            """,
            [job_run_id],
        )
    finally:
        con.close()


__all__ = [
    "EXECUTORS",
    "ExecutionArtifact",
    "ExecutionResult",
    "Executor",
    "RunnerTick",
    "claim_next",
    "compute_backoff_seconds",
    "default_worker_id",
    "list_run_artifacts",
    "load_run",
    "register_executor",
    "replay_failed_run",
    "run_worker_once",
    "run_worker_serve",
]


# Silence ``datetime`` unused-import warnings on static analyzers; the symbol
# is re-exported implicitly for callers that type-annotate policy math.
_ = datetime
