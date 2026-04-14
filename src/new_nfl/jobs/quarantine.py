"""Quarantine domain (T2.3C, ADR-0028).

First-class persistence for data-integrity incidents. A quarantine case is
opened whenever a pipeline step would otherwise have to silently drop or
mis-handle a record. Recovery is auditable via ``meta.recovery_action`` and
either references the new ``meta.job_run`` produced by a replay or marks the
case as overridden / suppressed by the operator.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from new_nfl._db import connect, new_id, row_to_dict
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings

CaseStatus = Literal["open", "in_progress", "resolved", "suppressed"]
ActionKind = Literal["replay", "override", "suppress"]
Severity = Literal["info", "warning", "error", "critical"]

OPEN_STATUSES: tuple[str, ...] = ("open", "in_progress")


class QuarantineCase(BaseModel):
    quarantine_case_id: str
    scope_type: str
    scope_ref: str
    reason_code: str
    severity: str
    evidence_refs_json: str = "[]"
    status: str
    owner: str | None = None
    notes: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecoveryAction(BaseModel):
    recovery_action_id: str
    quarantine_case_id: str
    action_kind: str
    triggered_by: str | None = None
    resulting_run_id: str | None = None
    note: str | None = None
    detail_json: str = "{}"
    triggered_at: datetime | None = None


# ---------------------------------------------------------------------------
# Open / dedupe
# ---------------------------------------------------------------------------


def open_quarantine_case(
    settings: Settings,
    *,
    scope_type: str,
    scope_ref: str,
    reason_code: str,
    severity: Severity = "error",
    evidence_refs: list[dict[str, Any]] | None = None,
    notes: str | None = None,
    owner: str | None = None,
) -> QuarantineCase:
    """Open a quarantine case or refresh an existing open one.

    Idempotency key = ``(scope_type, scope_ref, reason_code)`` while the case
    is still in an open status (``open`` / ``in_progress``). A re-occurrence
    bumps ``last_seen_at`` and merges any new evidence_refs by appending.
    """
    ensure_metadata_surface(settings)
    refs_payload = json.dumps(
        evidence_refs or [], sort_keys=True, ensure_ascii=False
    )
    con = connect(settings)
    try:
        existing = row_to_dict(
            con,
            f"""
            SELECT *
            FROM meta.quarantine_case
            WHERE scope_type = ?
              AND scope_ref = ?
              AND reason_code = ?
              AND status IN ({",".join("?" * len(OPEN_STATUSES))})
            ORDER BY first_seen_at DESC
            LIMIT 1
            """,
            [scope_type, scope_ref, reason_code, *OPEN_STATUSES],
        )
        if existing:
            case_id = existing[0]["quarantine_case_id"]
            merged_refs = json.loads(existing[0].get("evidence_refs_json") or "[]")
            for ref in evidence_refs or []:
                if ref not in merged_refs:
                    merged_refs.append(ref)
            con.execute(
                """
                UPDATE meta.quarantine_case
                SET last_seen_at = current_timestamp,
                    evidence_refs_json = ?,
                    severity = CASE
                        WHEN severity = 'critical' THEN severity
                        WHEN ? = 'critical' THEN ?
                        WHEN severity = 'error' THEN severity
                        WHEN ? = 'error' THEN ?
                        ELSE severity
                    END,
                    notes = COALESCE(?, notes),
                    owner = COALESCE(?, owner),
                    updated_at = current_timestamp
                WHERE quarantine_case_id = ?
                """,
                [
                    json.dumps(merged_refs, sort_keys=True, ensure_ascii=False),
                    severity, severity,
                    severity, severity,
                    notes,
                    owner,
                    case_id,
                ],
            )
        else:
            case_id = new_id()
            con.execute(
                """
                INSERT INTO meta.quarantine_case
                    (quarantine_case_id, scope_type, scope_ref, reason_code,
                     severity, evidence_refs_json, status, owner, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                [
                    case_id,
                    scope_type,
                    scope_ref,
                    reason_code,
                    severity,
                    refs_payload,
                    owner,
                    notes,
                ],
            )
        rows = row_to_dict(
            con,
            "SELECT * FROM meta.quarantine_case WHERE quarantine_case_id = ?",
            [case_id],
        )
        return QuarantineCase.model_validate(rows[0])
    finally:
        con.close()


# ---------------------------------------------------------------------------
# List / describe
# ---------------------------------------------------------------------------


def list_quarantine_cases(
    settings: Settings,
    *,
    status_filter: str = "open",
) -> list[QuarantineCase]:
    """List quarantine cases.

    ``status_filter`` accepts a concrete status, ``open`` (= open OR
    in_progress) or ``all``.
    """
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        if status_filter == "all":
            sql = (
                "SELECT * FROM meta.quarantine_case "
                "ORDER BY first_seen_at DESC"
            )
            params: list[Any] = []
        elif status_filter == "open":
            sql = (
                "SELECT * FROM meta.quarantine_case "
                f"WHERE status IN ({','.join('?' * len(OPEN_STATUSES))}) "
                "ORDER BY first_seen_at DESC"
            )
            params = list(OPEN_STATUSES)
        else:
            sql = (
                "SELECT * FROM meta.quarantine_case "
                "WHERE status = ? ORDER BY first_seen_at DESC"
            )
            params = [status_filter]
        rows = row_to_dict(con, sql, params)
        return [QuarantineCase.model_validate(r) for r in rows]
    finally:
        con.close()


def describe_quarantine_case(
    settings: Settings, quarantine_case_id: str
) -> dict[str, Any] | None:
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        case_rows = row_to_dict(
            con,
            "SELECT * FROM meta.quarantine_case WHERE quarantine_case_id = ?",
            [quarantine_case_id],
        )
        if not case_rows:
            return None
        case = QuarantineCase.model_validate(case_rows[0])
        action_rows = row_to_dict(
            con,
            """
            SELECT * FROM meta.recovery_action
            WHERE quarantine_case_id = ?
            ORDER BY triggered_at
            """,
            [quarantine_case_id],
        )
        actions = [RecoveryAction.model_validate(r) for r in action_rows]
        return {"case": case, "actions": actions}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


def resolve_quarantine_case(
    settings: Settings,
    *,
    quarantine_case_id: str,
    action: ActionKind,
    note: str | None = None,
    triggered_by: str = "operator",
    worker_id: str | None = None,
) -> dict[str, Any]:
    """Resolve a quarantine case.

    - ``replay``: requires ``scope_type='job_run'``. Re-runs the failed job
      via the runner and links the new ``job_run_id`` into the recovery
      action. The case is closed only if the replay succeeds — otherwise it
      stays open and a new failed run is auto-quarantined by the runner.
    - ``override``: closes the case as ``resolved`` without a new run.
    - ``suppress``: closes the case as ``suppressed`` (operator decided to
      ignore future occurrences with the same shape).
    """
    ensure_metadata_surface(settings)
    detail = describe_quarantine_case(settings, quarantine_case_id)
    if detail is None:
        raise ValueError(f"unknown quarantine_case_id={quarantine_case_id}")
    case: QuarantineCase = detail["case"]
    if case.status in ("resolved", "suppressed"):
        raise ValueError(
            f"case {quarantine_case_id} already in terminal status {case.status}"
        )

    resulting_run_id: str | None = None
    replay_status: str | None = None

    if action == "replay":
        if case.scope_type != "job_run":
            raise ValueError(
                "replay only supported for cases with scope_type='job_run'; "
                f"got scope_type={case.scope_type!r}"
            )
        # Lazy import to avoid the (jobs.runner -> jobs.__init__ -> quarantine)
        # cycle when this module is imported by the runner.
        from new_nfl.jobs.runner import replay_failed_run

        tick = replay_failed_run(
            settings,
            job_run_id=case.scope_ref,
            worker_id=worker_id or "cli-quarantine-replay",
        )
        resulting_run_id = tick.job_run_id
        replay_status = tick.run_status

    con = connect(settings)
    try:
        action_id = new_id()
        con.execute(
            """
            INSERT INTO meta.recovery_action
                (recovery_action_id, quarantine_case_id, action_kind,
                 triggered_by, resulting_run_id, note, detail_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                action_id,
                quarantine_case_id,
                action,
                triggered_by,
                resulting_run_id,
                note,
                json.dumps(
                    {"replay_status": replay_status} if replay_status else {},
                    sort_keys=True,
                    ensure_ascii=False,
                ),
            ],
        )
        if action == "suppress":
            new_status = "suppressed"
            close = True
        elif action == "override":
            new_status = "resolved"
            close = True
        else:  # replay
            if replay_status == "success":
                new_status = "resolved"
                close = True
            else:
                # Replay did not succeed — keep the case open so the operator
                # can decide on the next move; the new failed run will have
                # opened its own auto-case via the runner hook.
                new_status = "in_progress"
                close = False
        con.execute(
            """
            UPDATE meta.quarantine_case
            SET status = ?,
                resolved_at = CASE WHEN ? THEN current_timestamp ELSE resolved_at END,
                updated_at = current_timestamp
            WHERE quarantine_case_id = ?
            """,
            [new_status, close, quarantine_case_id],
        )
    finally:
        con.close()

    refreshed = describe_quarantine_case(settings, quarantine_case_id)
    return {
        "case": refreshed["case"] if refreshed else None,
        "actions": refreshed["actions"] if refreshed else [],
        "resulting_run_id": resulting_run_id,
        "replay_status": replay_status,
    }


__all__ = [
    "ActionKind",
    "CaseStatus",
    "OPEN_STATUSES",
    "QuarantineCase",
    "RecoveryAction",
    "Severity",
    "describe_quarantine_case",
    "list_quarantine_cases",
    "open_quarantine_case",
    "resolve_quarantine_case",
]
