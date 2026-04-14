"""Quarantine domain + runner integration tests (T2.3C, ADR-0028)."""
from __future__ import annotations

import json
import sys

import duckdb
import pytest

from new_nfl._db import connect, row_to_dict
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli import build_parser, main
from new_nfl.jobs import (
    EXECUTORS,
    describe_quarantine_case,
    enqueue_job,
    list_quarantine_cases,
    open_quarantine_case,
    register_executor,
    register_job,
    register_retry_policy,
    resolve_quarantine_case,
    run_worker_once,
)
from new_nfl.jobs.runner import ExecutionArtifact, ExecutionResult
from new_nfl.settings import load_settings


EXPECTED_QUARANTINE_TABLES = ("quarantine_case", "recovery_action")


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _restore_executor(job_type: str):
    saved = EXECUTORS.get(job_type)
    def _cleanup():
        if saved is None:
            EXECUTORS.pop(job_type, None)
        else:
            EXECUTORS[job_type] = saved
    return _cleanup


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_bootstrap_creates_quarantine_tables(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'meta'
            """
        ).fetchall()
    finally:
        con.close()
    tables = {r[0] for r in rows}
    for table in EXPECTED_QUARANTINE_TABLES:
        assert table in tables, f"missing meta.{table}"


# ---------------------------------------------------------------------------
# open / dedupe
# ---------------------------------------------------------------------------


def test_open_quarantine_dedupes_open_case(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    first = open_quarantine_case(
        settings,
        scope_type='source_file',
        scope_ref='sf-123',
        reason_code='parser_error',
        severity='warning',
        evidence_refs=[{'kind': 'file', 'path': '/tmp/a.csv'}],
    )
    second = open_quarantine_case(
        settings,
        scope_type='source_file',
        scope_ref='sf-123',
        reason_code='parser_error',
        severity='error',
        evidence_refs=[{'kind': 'file', 'path': '/tmp/a.csv'},
                       {'kind': 'log', 'line': 42}],
        notes='second occurrence',
    )
    assert first.quarantine_case_id == second.quarantine_case_id
    # severity escalates warning -> error
    assert second.severity == 'error'
    refs = json.loads(second.evidence_refs_json)
    assert len(refs) == 2
    assert second.notes == 'second occurrence'


def test_open_after_resolve_creates_new_case(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    first = open_quarantine_case(
        settings,
        scope_type='manual',
        scope_ref='ref-1',
        reason_code='manual_check',
    )
    resolve_quarantine_case(
        settings,
        quarantine_case_id=first.quarantine_case_id,
        action='override',
        note='ok',
    )
    second = open_quarantine_case(
        settings,
        scope_type='manual',
        scope_ref='ref-1',
        reason_code='manual_check',
    )
    assert second.quarantine_case_id != first.quarantine_case_id
    assert second.status == 'open'


def test_list_status_filters(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    a = open_quarantine_case(
        settings, scope_type='x', scope_ref='1', reason_code='r',
    )
    open_quarantine_case(
        settings, scope_type='x', scope_ref='2', reason_code='r',
    )
    resolve_quarantine_case(
        settings,
        quarantine_case_id=a.quarantine_case_id,
        action='suppress',
        note='shut up',
    )
    open_cases = list_quarantine_cases(settings, status_filter='open')
    suppressed = list_quarantine_cases(settings, status_filter='suppressed')
    all_cases = list_quarantine_cases(settings, status_filter='all')
    assert {c.scope_ref for c in open_cases} == {'2'}
    assert {c.scope_ref for c in suppressed} == {'1'}
    assert len(all_cases) == 2


# ---------------------------------------------------------------------------
# resolve actions
# ---------------------------------------------------------------------------


def test_resolve_override_records_action(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    case = open_quarantine_case(
        settings, scope_type='x', scope_ref='1', reason_code='r',
    )
    result = resolve_quarantine_case(
        settings,
        quarantine_case_id=case.quarantine_case_id,
        action='override',
        note='operator decided',
        triggered_by='operator',
    )
    assert result['case'].status == 'resolved'
    assert len(result['actions']) == 1
    assert result['actions'][0].action_kind == 'override'
    assert result['resulting_run_id'] is None


def test_resolve_replay_requires_job_run_scope(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    case = open_quarantine_case(
        settings, scope_type='source_file', scope_ref='sf-1', reason_code='r',
    )
    with pytest.raises(ValueError):
        resolve_quarantine_case(
            settings,
            quarantine_case_id=case.quarantine_case_id,
            action='replay',
        )


def test_resolve_terminal_case_rejected(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    case = open_quarantine_case(
        settings, scope_type='x', scope_ref='1', reason_code='r',
    )
    resolve_quarantine_case(
        settings,
        quarantine_case_id=case.quarantine_case_id,
        action='override',
    )
    with pytest.raises(ValueError):
        resolve_quarantine_case(
            settings,
            quarantine_case_id=case.quarantine_case_id,
            action='override',
        )


# ---------------------------------------------------------------------------
# Runner integration: failed runs auto-open quarantine
# ---------------------------------------------------------------------------


def test_runner_failure_auto_opens_quarantine_case(tmp_path, monkeypatch) -> None:
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
        job_key='boom',
        job_type='boom_test',
        retry_policy_key='only_one',
    )
    enqueue_job(settings, job_key='boom', params={})

    def _boom(settings_, params):
        raise RuntimeError('parser exploded')

    register_executor('boom_test', _boom)
    cleanup = _restore_executor('boom_test')
    try:
        tick = run_worker_once(settings, worker_id='w')
    finally:
        cleanup()
    assert tick.run_status == 'failed'
    assert tick.job_run_id is not None

    open_cases = list_quarantine_cases(settings, status_filter='open')
    assert len(open_cases) == 1
    case = open_cases[0]
    assert case.scope_type == 'job_run'
    assert case.scope_ref == tick.job_run_id
    assert case.reason_code == 'runner_exhausted'
    refs = json.loads(case.evidence_refs_json)
    assert refs[0]['job_key'] == 'boom'


def test_quarantine_replay_resolves_case_on_success(tmp_path, monkeypatch) -> None:
    """DoD: künstlich erzeugter Parser-Fehler landet in Quarantäne, Resolve
    erzeugt nachweisbar neuen Run."""
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
        job_key='replay_quarantine_probe',
        job_type='replay_quarantine_probe_test',
        retry_policy_key='only_one',
    )
    enqueue_job(
        settings, job_key='replay_quarantine_probe', params={'seed': 'x'},
    )

    state = {'should_fail': True}

    def _executor(settings_, params):
        if state['should_fail']:
            raise RuntimeError('parser_error: bad row 7')
        return ExecutionResult(
            success=True,
            message='ok',
            detail={'rows': 1},
            artifacts=[ExecutionArtifact(artifact_kind='out', ref_id='1')],
        )

    register_executor('replay_quarantine_probe_test', _executor)
    cleanup = _restore_executor('replay_quarantine_probe_test')
    try:
        first = run_worker_once(settings, worker_id='w')
        assert first.run_status == 'failed'

        cases = list_quarantine_cases(settings, status_filter='open')
        assert len(cases) == 1
        case_id = cases[0].quarantine_case_id

        # Operator flips the underlying defect, then resolves with replay.
        state['should_fail'] = False
        result = resolve_quarantine_case(
            settings,
            quarantine_case_id=case_id,
            action='replay',
            note='re-tried after fix',
            triggered_by='cli',
        )
    finally:
        cleanup()

    assert result['replay_status'] == 'success'
    assert result['resulting_run_id'] is not None
    assert result['resulting_run_id'] != first.job_run_id
    assert result['case'].status == 'resolved'

    # The recovery_action row links the case to the new run.
    detail = describe_quarantine_case(settings, case_id)
    assert detail is not None
    actions = detail['actions']
    assert len(actions) == 1
    assert actions[0].action_kind == 'replay'
    assert actions[0].resulting_run_id == result['resulting_run_id']

    # No new open case for the (now-successful) replay run.
    open_cases_after = list_quarantine_cases(settings, status_filter='open')
    assert open_cases_after == []


def test_quarantine_replay_failed_keeps_case_in_progress(
    tmp_path, monkeypatch
) -> None:
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
        job_key='still_failing',
        job_type='still_failing_test',
        retry_policy_key='only_one',
    )
    enqueue_job(settings, job_key='still_failing', params={})

    def _always_fail(settings_, params):
        raise RuntimeError('still broken')

    register_executor('still_failing_test', _always_fail)
    cleanup = _restore_executor('still_failing_test')
    try:
        first = run_worker_once(settings, worker_id='w')
        cases = list_quarantine_cases(settings, status_filter='open')
        case_id = cases[0].quarantine_case_id
        result = resolve_quarantine_case(
            settings,
            quarantine_case_id=case_id,
            action='replay',
            note='hopeful retry',
        )
    finally:
        cleanup()
    assert result['replay_status'] == 'failed'
    # Original case is in_progress (the replay didn't fix it). The runner
    # also auto-opened a *new* case for the new failed run.
    detail = describe_quarantine_case(settings, case_id)
    assert detail['case'].status == 'in_progress'
    open_cases = list_quarantine_cases(settings, status_filter='open')
    open_ids = {c.quarantine_case_id for c in open_cases}
    assert case_id in open_ids
    assert len(open_ids) >= 2  # original (in_progress) + new failure
    _ = first


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_parser_includes_quarantine_commands() -> None:
    parser = build_parser()
    args = parser.parse_args(['list-quarantine', '--status', 'all'])
    assert args.command == 'list-quarantine'
    assert args.status == 'all'

    show = parser.parse_args(['quarantine-show', '--quarantine-case-id', 'abc'])
    assert show.command == 'quarantine-show'

    resolve = parser.parse_args([
        'quarantine-resolve',
        '--quarantine-case-id', 'abc',
        '--action', 'override',
        '--note', 'ok',
    ])
    assert resolve.action == 'override'


def test_cli_list_quarantine_empty(tmp_path, monkeypatch, capsys) -> None:
    _bootstrap(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['new-nfl', 'list-quarantine'])
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'CASE_COUNT=0' in out


def test_cli_quarantine_show_and_resolve_override(
    tmp_path, monkeypatch, capsys
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    case = open_quarantine_case(
        settings, scope_type='manual', scope_ref='m1', reason_code='r',
        notes='check this',
    )

    monkeypatch.setattr(
        sys, 'argv',
        ['new-nfl', 'quarantine-show',
         '--quarantine-case-id', case.quarantine_case_id],
    )
    assert main() == 0
    out = capsys.readouterr().out
    assert f'QUARANTINE_CASE_ID={case.quarantine_case_id}' in out
    assert 'STATUS=open' in out
    assert 'NOTES=check this' in out
    assert 'ACTION_COUNT=0' in out

    monkeypatch.setattr(
        sys, 'argv',
        ['new-nfl', 'quarantine-resolve',
         '--quarantine-case-id', case.quarantine_case_id,
         '--action', 'override',
         '--note', 'looked at it'],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'NEW_STATUS=resolved' in out

    # Verify the recovery_action persisted
    con = connect(settings)
    try:
        rows = row_to_dict(
            con,
            "SELECT action_kind, note FROM meta.recovery_action WHERE quarantine_case_id = ?",
            [case.quarantine_case_id],
        )
    finally:
        con.close()
    assert rows == [{'action_kind': 'override', 'note': 'looked at it'}]
