import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.jobs import (
    describe_job,
    enqueue_job,
    list_jobs,
    register_job,
    register_retry_policy,
    upsert_schedule,
)
from new_nfl.settings import load_settings

EXPECTED_JOB_TABLES = (
    "retry_policy",
    "job_definition",
    "job_schedule",
    "job_queue",
    "job_run",
    "run_event",
    "run_artifact",
)


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def test_bootstrap_creates_job_tables(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'meta'
            """
        ).fetchall()
    finally:
        con.close()
    tables = {row[0] for row in rows}
    for table in EXPECTED_JOB_TABLES:
        assert table in tables, f"missing meta.{table}"


def test_register_retry_policy_is_idempotent(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    first = register_retry_policy(
        settings,
        policy_key='default_exp',
        max_attempts=5,
        backoff_kind='exponential',
        base_seconds=30,
        max_seconds=3600,
        jitter_ratio=0.2,
        notes='default exponential backoff',
    )
    second = register_retry_policy(
        settings,
        policy_key='default_exp',
        max_attempts=7,
        backoff_kind='exponential',
        base_seconds=60,
    )
    assert first.retry_policy_id == second.retry_policy_id
    assert second.max_attempts == 7
    assert second.base_seconds == 60


def test_register_job_requires_known_retry_policy(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        register_job(
            settings,
            job_key='fetch_x',
            job_type='fetch_remote',
            retry_policy_key='does_not_exist',
        )


def test_register_and_describe_job_with_schedule(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_retry_policy(
        settings,
        policy_key='fetch_default',
        max_attempts=3,
        backoff_kind='exponential',
        base_seconds=60,
    )
    job = register_job(
        settings,
        job_key='fetch_nflverse_bulk',
        job_type='fetch_remote',
        target_ref='nflverse_bulk',
        description='Fetch nflverse bulk datasets',
        concurrency_key='nflverse_bulk',
        params={'remote_url': ''},
        retry_policy_key='fetch_default',
    )
    assert job.retry_policy_id is not None

    upsert_schedule(
        settings,
        job_key='fetch_nflverse_bulk',
        schedule_kind='cron',
        schedule_expr='0 6 * * *',
        timezone='Europe/Berlin',
    )

    all_jobs = list_jobs(settings)
    assert len(all_jobs) == 1
    assert all_jobs[0].job_key == 'fetch_nflverse_bulk'

    described = describe_job(settings, 'fetch_nflverse_bulk')
    assert described is not None
    assert described['job'].target_ref == 'nflverse_bulk'
    assert described['retry_policy'] is not None
    assert described['retry_policy'].policy_key == 'fetch_default'
    assert len(described['schedules']) == 1
    assert described['schedules'][0].schedule_expr == '0 6 * * *'
    assert described['recent_runs'] == []


def test_describe_job_unknown_returns_none(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    assert describe_job(settings, 'nope') is None


def test_enqueue_job_deduplicates_by_idempotency_key(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(
        settings,
        job_key='stage_load_bulk',
        job_type='stage_load',
        target_ref='nflverse_bulk',
    )

    first = enqueue_job(
        settings,
        job_key='stage_load_bulk',
        idempotency_key='run-2026-04-13',
        params={'adapter_id': 'nflverse_bulk'},
    )
    second = enqueue_job(
        settings,
        job_key='stage_load_bulk',
        idempotency_key='run-2026-04-13',
        params={'adapter_id': 'nflverse_bulk'},
    )
    assert first.queue_item_id == second.queue_item_id
    assert first.claim_status == 'pending'


def test_register_job_upsert_updates_fields(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    first = register_job(
        settings,
        job_key='maintenance_vacuum',
        job_type='maintenance',
        description='first',
    )
    second = register_job(
        settings,
        job_key='maintenance_vacuum',
        job_type='maintenance',
        description='second',
        is_active=False,
    )
    assert first.job_id == second.job_id
    assert second.description == 'second'
    assert second.is_active is False
