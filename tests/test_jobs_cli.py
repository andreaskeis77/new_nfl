from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli import build_parser, main
from new_nfl.jobs import register_job, register_retry_policy, upsert_schedule
from new_nfl.settings import load_settings


def test_cli_parser_includes_job_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(['list-jobs']).command == 'list-jobs'

    described = parser.parse_args(['describe-job', '--job-key', 'fetch_nflverse_bulk'])
    assert described.command == 'describe-job'
    assert described.job_key == 'fetch_nflverse_bulk'

    registered = parser.parse_args(
        [
            'register-job',
            '--job-key', 'fetch_nflverse_bulk',
            '--job-type', 'fetch_remote',
            '--target-ref', 'nflverse_bulk',
        ]
    )
    assert registered.command == 'register-job'
    assert registered.job_key == 'fetch_nflverse_bulk'
    assert registered.job_type == 'fetch_remote'
    assert registered.target_ref == 'nflverse_bulk'
    assert registered.inactive is False

    policy = parser.parse_args(
        [
            'register-retry-policy',
            '--policy-key', 'fetch_default',
            '--max-attempts', '3',
            '--backoff-kind', 'exponential',
            '--base-seconds', '60',
        ]
    )
    assert policy.command == 'register-retry-policy'
    assert policy.max_attempts == 3


def test_cli_list_jobs_empty(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)

    monkeypatch.setattr('sys.argv', ['new-nfl', 'list-jobs'])
    rc = main()
    captured = capsys.readouterr()
    assert rc == 0
    assert 'JOB_COUNT=0' in captured.out


def test_cli_describe_job_prints_schedule_and_policy(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)

    register_retry_policy(
        settings,
        policy_key='fetch_default',
        max_attempts=3,
        backoff_kind='exponential',
        base_seconds=60,
    )
    register_job(
        settings,
        job_key='fetch_nflverse_bulk',
        job_type='fetch_remote',
        target_ref='nflverse_bulk',
        retry_policy_key='fetch_default',
    )
    upsert_schedule(
        settings,
        job_key='fetch_nflverse_bulk',
        schedule_kind='cron',
        schedule_expr='0 6 * * *',
        timezone='Europe/Berlin',
    )

    monkeypatch.setattr(
        'sys.argv',
        ['new-nfl', 'describe-job', '--job-key', 'fetch_nflverse_bulk'],
    )
    rc = main()
    captured = capsys.readouterr()
    assert rc == 0
    assert 'JOB_KEY=fetch_nflverse_bulk' in captured.out
    assert 'JOB_TYPE=fetch_remote' in captured.out
    assert 'RETRY_POLICY=fetch_default' in captured.out
    assert 'SCHEDULE_COUNT=1' in captured.out
    assert '0 6 * * *' in captured.out
    assert 'RECENT_RUN_COUNT=0' in captured.out


def test_cli_describe_job_unknown_returns_1(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)

    monkeypatch.setattr(
        'sys.argv',
        ['new-nfl', 'describe-job', '--job-key', 'nope'],
    )
    rc = main()
    captured = capsys.readouterr()
    assert rc == 1
    assert 'STATUS=not_found' in captured.out


def test_cli_register_job_roundtrip(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)

    monkeypatch.setattr(
        'sys.argv',
        [
            'new-nfl', 'register-retry-policy',
            '--policy-key', 'fetch_default',
            '--max-attempts', '3',
            '--backoff-kind', 'exponential',
            '--base-seconds', '60',
        ],
    )
    assert main() == 0
    capsys.readouterr()

    monkeypatch.setattr(
        'sys.argv',
        [
            'new-nfl', 'register-job',
            '--job-key', 'fetch_nflverse_bulk',
            '--job-type', 'fetch_remote',
            '--target-ref', 'nflverse_bulk',
            '--description', 'Fetch bulk',
            '--concurrency-key', 'nflverse_bulk',
            '--params-json', '{"remote_url":""}',
            '--retry-policy-key', 'fetch_default',
        ],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'STATUS=registered' in out

    monkeypatch.setattr('sys.argv', ['new-nfl', 'list-jobs'])
    assert main() == 0
    out = capsys.readouterr().out
    assert 'JOB_COUNT=1' in out
    assert 'fetch_nflverse_bulk' in out
