"""Tests for the internal job runner (T2.3B)."""
from __future__ import annotations

import threading
from typing import Any

import duckdb
import pytest

from new_nfl._db import connect, row_to_dict
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.jobs import (
    enqueue_job,
    register_executor,
    register_job,
    register_retry_policy,
)
from new_nfl.jobs.runner import (
    EXECUTORS,
    ExecutionArtifact,
    ExecutionResult,
    _claim_one,
    claim_next,
    compute_backoff_seconds,
    list_run_artifacts,
    load_run,
    replay_failed_run,
    run_worker_once,
    run_worker_serve,
)
from new_nfl.settings import load_settings


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _restore_executor(job_type: str):
    """Return a fixture-style cleanup to restore an overridden executor."""
    saved = EXECUTORS.get(job_type)
    def _cleanup():
        if saved is None:
            EXECUTORS.pop(job_type, None)
        else:
            EXECUTORS[job_type] = saved
    return _cleanup


# ---------------------------------------------------------------------------
# Backoff math
# ---------------------------------------------------------------------------


def test_compute_backoff_exponential_respects_cap(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    policy = register_retry_policy(
        settings,
        policy_key='exp_capped',
        max_attempts=5,
        backoff_kind='exponential',
        base_seconds=30,
        max_seconds=120,
    )
    assert compute_backoff_seconds(policy, attempt_number=1) == 30
    assert compute_backoff_seconds(policy, attempt_number=2) == 60
    assert compute_backoff_seconds(policy, attempt_number=3) == 120  # capped
    assert compute_backoff_seconds(policy, attempt_number=5) == 120  # capped


def test_compute_backoff_linear_and_fixed(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    linear = register_retry_policy(
        settings,
        policy_key='linear',
        max_attempts=3,
        backoff_kind='linear',
        base_seconds=10,
    )
    fixed = register_retry_policy(
        settings,
        policy_key='fixed',
        max_attempts=3,
        backoff_kind='fixed',
        base_seconds=7,
    )
    assert compute_backoff_seconds(linear, 1) == 10
    assert compute_backoff_seconds(linear, 3) == 30
    assert compute_backoff_seconds(fixed, 5) == 7


# ---------------------------------------------------------------------------
# Basic claim + execute
# ---------------------------------------------------------------------------


def test_run_worker_once_is_idle_when_queue_empty(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    tick = run_worker_once(settings, worker_id='test')
    assert tick.claimed is False
    assert tick.job_run_id is None


def test_custom_executor_runs_and_writes_evidence(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(
        settings,
        job_key='custom_deterministic',
        job_type='custom',
    )
    enqueue_job(
        settings,
        job_key='custom_deterministic',
        params={'seed': 'alpha'},
    )
    tick = run_worker_once(settings, worker_id='test')
    assert tick.claimed is True
    assert tick.run_status == 'success'
    assert tick.job_run_id is not None

    run = load_run(settings, tick.job_run_id)
    assert run is not None
    assert run.run_status == 'success'
    assert run.attempt_number == 1
    assert run.worker_id == 'test'

    artifacts = list_run_artifacts(settings, tick.job_run_id)
    assert len(artifacts) == 1
    assert artifacts[0]['artifact_kind'] == 'custom_output'


# ---------------------------------------------------------------------------
# Atomic claim — two concurrent workers, only one wins
# ---------------------------------------------------------------------------


def test_claim_atomic_only_one_worker_wins(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(
        settings,
        job_key='atomic_probe',
        job_type='custom',
    )
    enqueue_job(
        settings,
        job_key='atomic_probe',
        params={'n': 1},
    )

    results: list[dict[str, Any] | None] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _worker(worker_id: str) -> None:
        try:
            con = connect(settings)
            try:
                barrier.wait(timeout=5)
                claimed = _claim_one(con, worker_id)
                results.append(claimed)
            finally:
                con.close()
        except BaseException as exc:  # pragma: no cover - propagated via list
            errors.append(exc)

    t1 = threading.Thread(target=_worker, args=('w-a',))
    t2 = threading.Thread(target=_worker, args=('w-b',))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Surface any thread-local errors but tolerate DuckDB write-serialization
    # exceptions which are themselves proof of mutual exclusion.
    fatal_errors = [
        e for e in errors
        if not isinstance(e, duckdb.Error)
    ]
    assert not fatal_errors, f"non-DuckDB error(s): {fatal_errors!r}"

    claims = [r for r in results if r is not None]
    assert len(claims) == 1, (
        f"expected exactly one winning claim, got {len(claims)} (results={results})"
    )
    # The total attempts across both workers may be 1 (loser saw no candidate)
    # or 2 (loser raised and rolled back). Either way the queue must reflect
    # exactly one claimed item.
    con = connect(settings)
    try:
        status_rows = row_to_dict(
            con,
            "SELECT claim_status, attempt_count FROM meta.job_queue",
        )
    finally:
        con.close()
    assert len(status_rows) == 1
    assert status_rows[0]['claim_status'] == 'claimed'
    assert status_rows[0]['attempt_count'] == 1


# ---------------------------------------------------------------------------
# Concurrency-key blocking
# ---------------------------------------------------------------------------


def test_concurrency_key_blocks_second_claim(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(
        settings,
        job_key='custom_block_a',
        job_type='custom',
        concurrency_key='shared',
    )
    register_job(
        settings,
        job_key='custom_block_b',
        job_type='custom',
        concurrency_key='shared',
    )
    enqueue_job(settings, job_key='custom_block_a', params={'n': 1})
    enqueue_job(settings, job_key='custom_block_b', params={'n': 2})

    first = claim_next(settings, worker_id='w1')
    assert first is not None
    # second claim must be blocked because concurrency_key 'shared' is held
    second = claim_next(settings, worker_id='w2')
    assert second is None


# ---------------------------------------------------------------------------
# Retry path
# ---------------------------------------------------------------------------


def test_retry_on_failure_then_success(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_retry_policy(
        settings,
        policy_key='fast_retry',
        max_attempts=3,
        backoff_kind='fixed',
        base_seconds=0,
    )
    register_job(
        settings,
        job_key='flaky',
        job_type='flaky_test',
        retry_policy_key='fast_retry',
    )
    enqueue_job(settings, job_key='flaky', params={})

    counter = {'attempts': 0}

    def _flaky(settings_, params):
        counter['attempts'] += 1
        if counter['attempts'] < 2:
            raise RuntimeError(f'forced failure #{counter["attempts"]}')
        return ExecutionResult(
            success=True,
            message='ok after retry',
            detail={'attempts': counter['attempts']},
            artifacts=[ExecutionArtifact(artifact_kind='flaky_output', ref_id='ok')],
        )

    register_executor('flaky_test', _flaky)
    cleanup = _restore_executor('flaky_test')
    try:
        first = run_worker_once(settings, worker_id='w')
        assert first.run_status == 'retrying'

        second = run_worker_once(settings, worker_id='w')
        assert second.run_status == 'success'
        assert counter['attempts'] == 2
    finally:
        cleanup()

    con = connect(settings)
    try:
        runs = row_to_dict(
            con,
            "SELECT run_status, attempt_number FROM meta.job_run ORDER BY attempt_number",
        )
        queue = row_to_dict(con, "SELECT claim_status, attempt_count FROM meta.job_queue")
    finally:
        con.close()
    assert [(r['run_status'], r['attempt_number']) for r in runs] == [
        ('retrying', 1),
        ('success', 2),
    ]
    assert queue[0]['claim_status'] == 'done'
    assert queue[0]['attempt_count'] == 2


def test_retry_exhausted_marks_queue_abandoned(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_retry_policy(
        settings,
        policy_key='only_one',
        max_attempts=1,
        backoff_kind='fixed',
        base_seconds=0,
    )
    register_job(
        settings,
        job_key='always_fails',
        job_type='always_fails_test',
        retry_policy_key='only_one',
    )
    enqueue_job(settings, job_key='always_fails', params={})

    def _fail(settings_, params):
        raise RuntimeError('nope')

    register_executor('always_fails_test', _fail)
    cleanup = _restore_executor('always_fails_test')
    try:
        tick = run_worker_once(settings, worker_id='w')
    finally:
        cleanup()
    assert tick.run_status == 'failed'

    con = connect(settings)
    try:
        queue = row_to_dict(con, "SELECT claim_status FROM meta.job_queue")
    finally:
        con.close()
    assert queue[0]['claim_status'] == 'abandoned'


# ---------------------------------------------------------------------------
# Replay determinism
# ---------------------------------------------------------------------------


def test_replay_failed_run_reproduces_deterministically(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_retry_policy(
        settings,
        policy_key='once',
        max_attempts=1,
        backoff_kind='fixed',
        base_seconds=0,
    )
    register_job(
        settings,
        job_key='replay_probe',
        job_type='replay_probe_test',
        retry_policy_key='once',
    )
    enqueue_job(
        settings,
        job_key='replay_probe',
        params={'seed': 'omega'},
    )

    state = {'should_fail': True}

    def _executor(settings_, params):
        if state['should_fail']:
            raise RuntimeError('simulated transient failure')
        import hashlib, json as _json
        digest = hashlib.sha256(
            _json.dumps(params, sort_keys=True).encode('utf-8')
        ).hexdigest()[:16]
        return ExecutionResult(
            success=True,
            message=f'deterministic digest={digest}',
            detail={'digest': digest},
            artifacts=[
                ExecutionArtifact(
                    artifact_kind='deterministic_output',
                    ref_id=digest,
                    detail={'params': params},
                )
            ],
        )

    register_executor('replay_probe_test', _executor)
    cleanup = _restore_executor('replay_probe_test')
    try:
        first = run_worker_once(settings, worker_id='w')
        assert first.run_status == 'failed'
        assert first.job_run_id is not None

        # Flip the failure switch — the replay must succeed and produce a
        # deterministic artifact keyed by the original params.
        state['should_fail'] = False
        replay = replay_failed_run(
            settings,
            job_run_id=first.job_run_id,
            worker_id='w-replay',
        )
    finally:
        cleanup()

    assert replay.run_status == 'success'
    assert replay.job_run_id is not None
    assert replay.job_run_id != first.job_run_id

    artifacts = list_run_artifacts(settings, replay.job_run_id)
    assert len(artifacts) == 1
    # Same params → same digest → deterministic ref_id
    import hashlib, json as _json
    expected_digest = hashlib.sha256(
        _json.dumps({'seed': 'omega'}, sort_keys=True).encode('utf-8')
    ).hexdigest()[:16]
    assert artifacts[0]['ref_id'] == expected_digest

    # The immutable evidence of the failed run is preserved — including the
    # replay_enqueued event linking old → new.
    con = connect(settings)
    try:
        events = row_to_dict(
            con,
            "SELECT event_kind FROM meta.run_event WHERE job_run_id = ? ORDER BY recorded_at",
            [first.job_run_id],
        )
    finally:
        con.close()
    event_kinds = [e['event_kind'] for e in events]
    assert 'run_started' in event_kinds
    assert 'retry_exhausted' in event_kinds
    assert 'replay_enqueued' in event_kinds


def test_replay_rejects_non_failed_run(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(settings, job_key='ok', job_type='custom')
    enqueue_job(settings, job_key='ok', params={})
    tick = run_worker_once(settings, worker_id='w')
    assert tick.run_status == 'success'
    assert tick.job_run_id is not None
    with pytest.raises(ValueError):
        replay_failed_run(settings, job_run_id=tick.job_run_id)


# ---------------------------------------------------------------------------
# serve mode smoke
# ---------------------------------------------------------------------------


def test_run_worker_serve_stops_when_idle(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(settings, job_key='serve_probe', job_type='custom')
    enqueue_job(settings, job_key='serve_probe', params={'n': 1})
    enqueue_job(
        settings,
        job_key='serve_probe',
        idempotency_key='second',
        params={'n': 2},
    )
    ticks = run_worker_serve(
        settings,
        worker_id='serve-w',
        idle_sleep_seconds=0.0,
        max_iterations=10,
        stop_when_idle=True,
    )
    claimed = [t for t in ticks if t.claimed]
    assert len(claimed) == 2
    assert all(t.run_status == 'success' for t in claimed)
    # last tick is the idle sentinel
    assert ticks[-1].claimed is False
