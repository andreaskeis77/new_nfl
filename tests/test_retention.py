"""Event-Retention-Tests (T2.7E-1).

Deckt die ``trim_run_events``-Backend-Funktion ab: abgeschlossene Runs
älter als N Tage verlieren ihre ``meta.run_event`` / ``meta.run_artifact``
-Feinspur; die ``meta.job_run``-Zeile selbst bleibt für Aggregate
erhalten.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from new_nfl._db import connect
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.meta.retention import (
    RetentionResult,
    parse_older_than,
    trim_run_events,
)
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import load_settings


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    ensure_metadata_surface(settings)
    return settings


def _seed_job_run(
    con,
    *,
    job_run_id: str,
    run_status: str,
    finished_at: datetime | None,
    job_id: str = "job-1",
    started_at: datetime | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO meta.job_run
            (job_run_id, job_id, queue_item_id, run_status, attempt_number,
             worker_id, message, detail_json, started_at, finished_at)
        VALUES (?, ?, NULL, ?, 1, 'w-1', NULL, '{}', ?, ?)
        """,
        [job_run_id, job_id, run_status, started_at or datetime(2024, 1, 1), finished_at],
    )


def _seed_event(con, *, run_event_id: str, job_run_id: str) -> None:
    con.execute(
        """
        INSERT INTO meta.run_event
            (run_event_id, job_run_id, event_kind, severity, message,
             detail_json, recorded_at)
        VALUES (?, ?, 'info', 'info', NULL, '{}', current_timestamp)
        """,
        [run_event_id, job_run_id],
    )


def _seed_artifact(con, *, run_artifact_id: str, job_run_id: str) -> None:
    con.execute(
        """
        INSERT INTO meta.run_artifact
            (run_artifact_id, job_run_id, artifact_kind, ref_id, ref_path,
             detail_json, recorded_at)
        VALUES (?, ?, 'log', NULL, NULL, '{}', current_timestamp)
        """,
        [run_artifact_id, job_run_id],
    )


# ---------------------------------------------------------------------------
# parse_older_than
# ---------------------------------------------------------------------------


def test_parse_older_than_integer():
    assert parse_older_than("30") == 30


def test_parse_older_than_day_suffix():
    assert parse_older_than("30d") == 30
    assert parse_older_than("7D") == 7


def test_parse_older_than_rejects_zero():
    with pytest.raises(ValueError):
        parse_older_than("0d")


def test_parse_older_than_rejects_negative():
    with pytest.raises(ValueError):
        parse_older_than("-1")


def test_parse_older_than_rejects_empty():
    with pytest.raises(ValueError):
        parse_older_than("")


def test_parse_older_than_rejects_hours():
    with pytest.raises(ValueError):
        parse_older_than("12h")


# ---------------------------------------------------------------------------
# trim_run_events
# ---------------------------------------------------------------------------


def test_trim_run_events_rejects_non_positive_days(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        trim_run_events(settings, older_than_days=0)


def test_trim_run_events_empty_db_is_noop(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    result = trim_run_events(settings, older_than_days=30)
    assert isinstance(result, RetentionResult)
    assert result.older_than_days == 30
    assert result.dry_run is False
    assert result.eligible_run_count == 0
    assert result.deleted_event_count == 0
    assert result.deleted_artifact_count == 0


def test_trim_run_events_deletes_old_terminal_runs_events(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    now = datetime.utcnow()
    old = now - timedelta(days=60)
    recent = now - timedelta(days=5)
    con = connect(settings)
    try:
        _seed_job_run(con, job_run_id="r-old", run_status="success", finished_at=old)
        _seed_job_run(con, job_run_id="r-recent", run_status="success", finished_at=recent)
        _seed_event(con, run_event_id="ev-old-1", job_run_id="r-old")
        _seed_event(con, run_event_id="ev-old-2", job_run_id="r-old")
        _seed_event(con, run_event_id="ev-recent-1", job_run_id="r-recent")
        _seed_artifact(con, run_artifact_id="a-old-1", job_run_id="r-old")
    finally:
        con.close()

    result = trim_run_events(settings, older_than_days=30)

    assert result.eligible_run_count == 1
    assert result.deleted_event_count == 2
    assert result.deleted_artifact_count == 1

    con = connect(settings)
    try:
        remaining_events = con.execute(
            "SELECT run_event_id FROM meta.run_event ORDER BY run_event_id"
        ).fetchall()
        remaining_artifacts = con.execute(
            "SELECT run_artifact_id FROM meta.run_artifact"
        ).fetchall()
        remaining_runs = con.execute(
            "SELECT job_run_id FROM meta.job_run ORDER BY job_run_id"
        ).fetchall()
    finally:
        con.close()

    assert [row[0] for row in remaining_events] == ["ev-recent-1"]
    assert remaining_artifacts == []
    # job_run row MUST survive so aggregates in mart.run_overview_v1 stay complete.
    assert [row[0] for row in remaining_runs] == ["r-old", "r-recent"]


def test_trim_run_events_ignores_still_running_run(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    old = datetime.utcnow() - timedelta(days=60)
    con = connect(settings)
    try:
        # `running` is not terminal — the event MUST survive even if the
        # started_at is old.
        _seed_job_run(
            con,
            job_run_id="r-running",
            run_status="running",
            finished_at=None,
            started_at=old,
        )
        _seed_event(con, run_event_id="ev-running", job_run_id="r-running")
    finally:
        con.close()

    result = trim_run_events(settings, older_than_days=30)
    assert result.eligible_run_count == 0
    assert result.deleted_event_count == 0


def test_trim_run_events_handles_quarantined_status(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    old = datetime.utcnow() - timedelta(days=60)
    con = connect(settings)
    try:
        _seed_job_run(
            con,
            job_run_id="r-quar",
            run_status="quarantined",
            finished_at=old,
        )
        _seed_event(con, run_event_id="ev-quar", job_run_id="r-quar")
    finally:
        con.close()

    result = trim_run_events(settings, older_than_days=30)
    assert result.eligible_run_count == 1
    assert result.deleted_event_count == 1


def test_trim_run_events_status_compare_case_insensitive(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    old = datetime.utcnow() - timedelta(days=60)
    con = connect(settings)
    try:
        _seed_job_run(
            con, job_run_id="r-mixed", run_status="Success", finished_at=old
        )
        _seed_event(con, run_event_id="ev-mixed", job_run_id="r-mixed")
    finally:
        con.close()

    result = trim_run_events(settings, older_than_days=30)
    assert result.deleted_event_count == 1


def test_trim_run_events_dry_run_does_not_delete(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    old = datetime.utcnow() - timedelta(days=60)
    con = connect(settings)
    try:
        _seed_job_run(
            con, job_run_id="r-old", run_status="failed", finished_at=old
        )
        _seed_event(con, run_event_id="ev-old", job_run_id="r-old")
        _seed_artifact(con, run_artifact_id="a-old", job_run_id="r-old")
    finally:
        con.close()

    result = trim_run_events(settings, older_than_days=30, dry_run=True)
    assert result.dry_run is True
    assert result.deleted_event_count == 1
    assert result.deleted_artifact_count == 1

    con = connect(settings)
    try:
        event_count = con.execute(
            "SELECT COUNT(*) FROM meta.run_event"
        ).fetchone()[0]
        artifact_count = con.execute(
            "SELECT COUNT(*) FROM meta.run_artifact"
        ).fetchone()[0]
    finally:
        con.close()

    # Dry-run keeps rows untouched.
    assert event_count == 1
    assert artifact_count == 1


def test_trim_run_events_is_idempotent(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    old = datetime.utcnow() - timedelta(days=60)
    con = connect(settings)
    try:
        _seed_job_run(
            con, job_run_id="r-old", run_status="success", finished_at=old
        )
        _seed_event(con, run_event_id="ev-old", job_run_id="r-old")
    finally:
        con.close()

    first = trim_run_events(settings, older_than_days=30)
    second = trim_run_events(settings, older_than_days=30)

    assert first.deleted_event_count == 1
    assert second.deleted_event_count == 0
    assert second.eligible_run_count == 1  # the run row is still there


def test_trim_run_events_creates_surface_on_fresh_db(tmp_path, monkeypatch):
    """The retention call must not fail when meta.* tables don't exist yet."""
    # Skip bootstrap — just set the repo root; retention should auto-create.
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    result = trim_run_events(settings, older_than_days=30)
    assert result.deleted_event_count == 0


def test_trim_run_events_older_than_window_respected(tmp_path, monkeypatch):
    """A 7-day window catches a 10-day-old run but not a 5-day-old one."""
    settings = _bootstrap(tmp_path, monkeypatch)
    now = datetime.utcnow()
    ten_days = now - timedelta(days=10)
    five_days = now - timedelta(days=5)
    con = connect(settings)
    try:
        _seed_job_run(
            con, job_run_id="r-10d", run_status="success", finished_at=ten_days
        )
        _seed_job_run(
            con, job_run_id="r-5d", run_status="success", finished_at=five_days
        )
        _seed_event(con, run_event_id="ev-10d", job_run_id="r-10d")
        _seed_event(con, run_event_id="ev-5d", job_run_id="r-5d")
    finally:
        con.close()

    result = trim_run_events(settings, older_than_days=7)
    assert result.deleted_event_count == 1

    con = connect(settings)
    try:
        rows = con.execute(
            "SELECT run_event_id FROM meta.run_event"
        ).fetchall()
    finally:
        con.close()

    assert [r[0] for r in rows] == ["ev-5d"]
