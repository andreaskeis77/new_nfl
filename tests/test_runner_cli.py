"""CLI-facing tests for the internal runner (T2.3B)."""
from __future__ import annotations

import sys

from new_nfl._db import connect, row_to_dict
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli import build_parser, main
from new_nfl.jobs import enqueue_job, register_job
from new_nfl.settings import load_settings


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def test_cli_parser_includes_runner_commands() -> None:
    parser = build_parser()
    once = parser.parse_args(['run-worker', '--once'])
    assert once.command == 'run-worker'
    assert once.once is True
    assert once.serve is False

    serve = parser.parse_args(['run-worker', '--serve', '--max-iterations', '3'])
    assert serve.serve is True
    assert serve.max_iterations == 3

    replay = parser.parse_args(['replay-run', '--job-run-id', 'abc'])
    assert replay.command == 'replay-run'
    assert replay.job_run_id == 'abc'


def test_cli_run_worker_once_executes_pending(tmp_path, monkeypatch, capsys) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(settings, job_key='cli_custom', job_type='custom')
    enqueue_job(settings, job_key='cli_custom', params={'tag': 'abc'})

    monkeypatch.setattr(sys, 'argv', ['new-nfl', 'run-worker', '--once'])
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'CLAIMED=yes' in out
    assert 'RUN_STATUS=success' in out
    assert 'JOB_KEY=cli_custom' in out


def test_cli_run_worker_once_idle(tmp_path, monkeypatch, capsys) -> None:
    _bootstrap(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['new-nfl', 'run-worker', '--once'])
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'CLAIMED=no' in out


def test_cli_run_worker_rejects_no_mode(tmp_path, monkeypatch, capsys) -> None:
    _bootstrap(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['new-nfl', 'run-worker'])
    rc = main()
    out = capsys.readouterr().out
    assert rc == 2
    assert 'STATUS=invalid_mode' in out


def test_cli_run_worker_serve_stops_when_idle(tmp_path, monkeypatch, capsys) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    register_job(settings, job_key='serve_cli', job_type='custom')
    enqueue_job(settings, job_key='serve_cli', params={'n': 1})

    monkeypatch.setattr(
        sys,
        'argv',
        [
            'new-nfl', 'run-worker', '--serve',
            '--max-iterations', '5',
            '--idle-sleep', '0',
            '--stop-when-idle',
        ],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'TICK_COUNT=' in out
    assert 'TICK_0_RUN_STATUS=success' in out


def test_cli_fetch_remote_routes_through_runner_records_job_run(
    tmp_path, monkeypatch, capsys
) -> None:
    """fetch-remote in dry-run mode must produce a meta.job_run row.

    Manifest §3.13: no dark background path — every CLI-triggered run leaves
    a trace. This test pins that invariant without needing network I/O.
    """
    settings = _bootstrap(tmp_path, monkeypatch)
    from new_nfl.metadata import seed_default_sources
    seed_default_sources(settings)

    monkeypatch.setattr(
        sys,
        'argv',
        [
            'new-nfl', 'fetch-remote',
            '--adapter-id', 'nflverse_bulk',
            # no --execute -> dry-run
        ],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'RUN_STATUS=planned_remote_fetch' in out
    assert 'RUN_MODE=dry_run' in out

    con = connect(settings)
    try:
        runs = row_to_dict(
            con,
            """
            SELECT r.run_status, d.job_key, d.job_type
            FROM meta.job_run r
            JOIN meta.job_definition d ON d.job_id = r.job_id
            """,
        )
        queue = row_to_dict(con, "SELECT claim_status FROM meta.job_queue")
    finally:
        con.close()
    assert len(runs) == 1
    assert runs[0]['run_status'] == 'success'
    assert runs[0]['job_type'] == 'fetch_remote'
    assert runs[0]['job_key'] == 'cli_fetch_remote__nflverse_bulk'
    assert queue[0]['claim_status'] == 'done'
