"""Event-Retention für abgeschlossene Runs (T2.7E-1).

Löscht ``meta.run_event``- und ``meta.run_artifact``-Zeilen für
``meta.job_run``-Einträge mit ``run_status`` in ``{success, failed,
quarantined}`` und ``finished_at < NOW() - INTERVAL '<N> days'``.

Motivation: ``meta.run_event`` wächst linear mit der Anzahl Runs —
Read-Evidence-Drill-Downs (``mart.run_overview_v1``) skalieren sonst auf
Dauer schlecht. Die ``meta.job_run``-Zeile selbst bleibt erhalten, damit
Aggregate-Counts (``run_count``, ``error_event_count`` im Overview-Mart)
historisch bleiben — nur die Feinspur (Events + Artefakte) wird
beschnitten.

Zwei Betriebsmodi:

* ``dry_run=True`` — zählt die Kandidaten, schreibt nichts.
* ``dry_run=False`` — löscht in einer Transaktion (zuerst
  ``run_artifact``, dann ``run_event``), commited atomar.

Idempotent: ein zweiter Lauf über dasselbe Fenster findet nichts mehr und
liefert Null-Counts zurück.
"""
from __future__ import annotations

from dataclasses import dataclass

from new_nfl._db import connect
from new_nfl.settings import Settings

_TERMINAL_STATUSES: tuple[str, ...] = ("success", "failed", "quarantined")


@dataclass(frozen=True)
class RetentionResult:
    older_than_days: int
    dry_run: bool
    eligible_run_count: int
    deleted_event_count: int
    deleted_artifact_count: int


def _ensure_retention_surface(con) -> None:
    """Create placeholder tables so the retention call never ``DESCRIBE``-races on a fresh DB."""
    con.execute("CREATE SCHEMA IF NOT EXISTS meta")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.job_run (
            job_run_id VARCHAR PRIMARY KEY,
            job_id VARCHAR NOT NULL,
            queue_item_id VARCHAR,
            run_status VARCHAR NOT NULL,
            attempt_number INTEGER,
            worker_id VARCHAR,
            message VARCHAR,
            detail_json VARCHAR,
            started_at TIMESTAMP DEFAULT current_timestamp,
            finished_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.run_event (
            run_event_id VARCHAR PRIMARY KEY,
            job_run_id VARCHAR NOT NULL,
            event_kind VARCHAR NOT NULL,
            severity VARCHAR,
            message VARCHAR,
            detail_json VARCHAR,
            recorded_at TIMESTAMP DEFAULT current_timestamp
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.run_artifact (
            run_artifact_id VARCHAR PRIMARY KEY,
            job_run_id VARCHAR NOT NULL,
            artifact_kind VARCHAR NOT NULL,
            ref_id VARCHAR,
            ref_path VARCHAR,
            detail_json VARCHAR,
            recorded_at TIMESTAMP DEFAULT current_timestamp
        )
        """
    )


def trim_run_events(
    settings: Settings,
    *,
    older_than_days: int,
    dry_run: bool = False,
) -> RetentionResult:
    """Delete terminal runs' event-/artifact-rows older than ``older_than_days``.

    The ``meta.job_run`` row itself is **not** deleted — aggregates in
    ``mart.run_overview_v1`` remain correct.
    """
    if older_than_days <= 0:
        raise ValueError(
            f"older_than_days must be positive, got {older_than_days!r}"
        )

    placeholders = ", ".join("?" * len(_TERMINAL_STATUSES))
    # DuckDB-Interval arithmetic: `NOW() - INTERVAL '<N> days'`.
    # Parametrising the interval literal is brittle across DuckDB versions;
    # we inline the integer after validating it above.
    cutoff_expr = f"CURRENT_TIMESTAMP - INTERVAL '{int(older_than_days)} days'"

    con = connect(settings)
    try:
        _ensure_retention_surface(con)

        eligible_sql = f"""
            SELECT COUNT(*)
            FROM meta.job_run
            WHERE LOWER(run_status) IN ({placeholders})
              AND finished_at IS NOT NULL
              AND finished_at < {cutoff_expr}
        """
        eligible = int(con.execute(eligible_sql, list(_TERMINAL_STATUSES)).fetchone()[0])

        event_count_sql = f"""
            SELECT COUNT(*)
            FROM meta.run_event e
            WHERE EXISTS (
                SELECT 1 FROM meta.job_run r
                WHERE r.job_run_id = e.job_run_id
                  AND LOWER(r.run_status) IN ({placeholders})
                  AND r.finished_at IS NOT NULL
                  AND r.finished_at < {cutoff_expr}
            )
        """
        event_count = int(
            con.execute(event_count_sql, list(_TERMINAL_STATUSES)).fetchone()[0]
        )

        artifact_count_sql = f"""
            SELECT COUNT(*)
            FROM meta.run_artifact a
            WHERE EXISTS (
                SELECT 1 FROM meta.job_run r
                WHERE r.job_run_id = a.job_run_id
                  AND LOWER(r.run_status) IN ({placeholders})
                  AND r.finished_at IS NOT NULL
                  AND r.finished_at < {cutoff_expr}
            )
        """
        artifact_count = int(
            con.execute(artifact_count_sql, list(_TERMINAL_STATUSES)).fetchone()[0]
        )

        if dry_run or (event_count == 0 and artifact_count == 0):
            return RetentionResult(
                older_than_days=older_than_days,
                dry_run=dry_run,
                eligible_run_count=eligible,
                deleted_event_count=event_count,
                deleted_artifact_count=artifact_count,
            )

        con.execute("BEGIN")
        try:
            con.execute(
                f"""
                DELETE FROM meta.run_artifact
                WHERE job_run_id IN (
                    SELECT job_run_id FROM meta.job_run
                    WHERE LOWER(run_status) IN ({placeholders})
                      AND finished_at IS NOT NULL
                      AND finished_at < {cutoff_expr}
                )
                """,
                list(_TERMINAL_STATUSES),
            )
            con.execute(
                f"""
                DELETE FROM meta.run_event
                WHERE job_run_id IN (
                    SELECT job_run_id FROM meta.job_run
                    WHERE LOWER(run_status) IN ({placeholders})
                      AND finished_at IS NOT NULL
                      AND finished_at < {cutoff_expr}
                )
                """,
                list(_TERMINAL_STATUSES),
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()

    return RetentionResult(
        older_than_days=older_than_days,
        dry_run=dry_run,
        eligible_run_count=eligible,
        deleted_event_count=event_count,
        deleted_artifact_count=artifact_count,
    )


def parse_older_than(spec: str) -> int:
    """Parse ``--older-than`` operator input into an integer day count.

    Accepts either a bare integer (``"30"``) or a ``"<N>d"`` / ``"<N>D"``
    suffix. Non-positive values raise ``ValueError``. Hours/weeks are
    **not** supported — keep the operator surface narrow; if retention
    ever needs sub-day resolution, extend the parser then.
    """
    if not spec:
        raise ValueError("--older-than must not be empty")
    cleaned = spec.strip().lower()
    if cleaned.endswith("d"):
        cleaned = cleaned[:-1]
    try:
        value = int(cleaned)
    except ValueError as exc:
        raise ValueError(
            f"--older-than must be '<N>' or '<N>d', got {spec!r}"
        ) from exc
    if value <= 0:
        raise ValueError(f"--older-than must be positive, got {spec!r}")
    return value


__all__ = [
    "RetentionResult",
    "parse_older_than",
    "trim_run_events",
]
