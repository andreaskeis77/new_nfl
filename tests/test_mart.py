"""Mart layer tests (T2.3D, ADR-0029)."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli import build_parser, main
from new_nfl.mart import (
    MART_SCHEDULE_FIELD_DICTIONARY_V1,
    build_schedule_field_dictionary_v1,
)
from new_nfl.settings import load_settings


READ_MODULES = (
    'src/new_nfl/core_browse.py',
    'src/new_nfl/core_lookup.py',
    'src/new_nfl/core_summary.py',
    'src/new_nfl/web_preview.py',
    'src/new_nfl/web_server.py',
    'src/new_nfl/web/__init__.py',
    'src/new_nfl/web/assets.py',
    'src/new_nfl/web/freshness.py',
    'src/new_nfl/web/game_view.py',
    'src/new_nfl/web/games_view.py',
    'src/new_nfl/web/player_view.py',
    'src/new_nfl/web/provenance_view.py',
    'src/new_nfl/web/renderer.py',
    'src/new_nfl/web/run_view.py',
    'src/new_nfl/web/team_view.py',
)


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_core(settings, rows):
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS core')
        con.execute(
            '''
            CREATE OR REPLACE TABLE core.schedule_field_dictionary (
                field VARCHAR,
                data_type VARCHAR,
                description VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _canonicalized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        con.executemany(
            '''
            INSERT INTO core.schedule_field_dictionary
              (field, data_type, description, _source_file_id, _adapter_id)
            VALUES (?, ?, ?, ?, ?)
            ''',
            rows,
        )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_builder_requires_core_table(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='core.schedule_field_dictionary'):
        build_schedule_field_dictionary_v1(settings)


def test_builder_projects_lowercased_filter_columns(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core(
        settings,
        [
            ('Game_ID', 'Numeric', 'Primary identifier', 'sf-1', 'nflverse_bulk'),
            ('  HOME_team  ', 'Character', 'Home', 'sf-1', 'nflverse_bulk'),
        ],
    )
    result = build_schedule_field_dictionary_v1(settings)
    assert result.qualified_table == MART_SCHEDULE_FIELD_DICTIONARY_V1
    assert result.row_count == 2
    assert result.source_row_count == 2

    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f'SELECT field, field_lower, data_type_lower, source_file_id, '
            f'source_adapter_id FROM {MART_SCHEDULE_FIELD_DICTIONARY_V1} '
            f'ORDER BY field_lower'
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        ('Game_ID', 'game_id', 'numeric', 'sf-1', 'nflverse_bulk'),
        ('  HOME_team  ', 'home_team', 'character', 'sf-1', 'nflverse_bulk'),
    ]


def test_builder_is_idempotent_on_rebuild(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core(
        settings,
        [('a', 'numeric', 'A', 'sf', 'nflverse_bulk')],
    )
    first = build_schedule_field_dictionary_v1(settings)
    second = build_schedule_field_dictionary_v1(settings)
    assert first.row_count == second.row_count == 1


# ---------------------------------------------------------------------------
# Runner integration
# ---------------------------------------------------------------------------


def test_runner_executor_mart_build_creates_projection(tmp_path, monkeypatch) -> None:
    from new_nfl.jobs import (
        enqueue_job,
        register_job,
        register_retry_policy,
        run_worker_once,
    )

    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core(
        settings,
        [('week', 'numeric', 'Week number', 'sf-1', 'nflverse_bulk')],
    )
    register_retry_policy(
        settings,
        policy_key='only_one',
        max_attempts=1,
        backoff_kind='fixed',
        base_seconds=0,
    )
    register_job(
        settings,
        job_key='mart_build_probe',
        job_type='mart_build',
        retry_policy_key='only_one',
    )
    enqueue_job(
        settings,
        job_key='mart_build_probe',
        params={'mart_key': 'schedule_field_dictionary_v1'},
    )
    tick = run_worker_once(settings, worker_id='w')
    assert tick.run_status == 'success', tick.message
    assert tick.detail['qualified_table'] == MART_SCHEDULE_FIELD_DICTIONARY_V1
    assert tick.detail['row_count'] == 1


def test_runner_executor_mart_build_rejects_unknown_key(tmp_path, monkeypatch) -> None:
    from new_nfl.jobs import (
        enqueue_job,
        register_job,
        register_retry_policy,
        run_worker_once,
    )

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
        job_key='mart_build_bad',
        job_type='mart_build',
        retry_policy_key='only_one',
    )
    enqueue_job(
        settings,
        job_key='mart_build_bad',
        params={'mart_key': 'does_not_exist'},
    )
    tick = run_worker_once(settings, worker_id='w')
    assert tick.run_status == 'failed'
    assert 'unknown mart_key' in (tick.message or '')


# ---------------------------------------------------------------------------
# core-load wires mart build
# ---------------------------------------------------------------------------


def test_core_load_execute_rebuilds_mart(tmp_path, monkeypatch) -> None:
    from new_nfl.core_load import execute_core_load

    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS stg')
        con.execute(
            '''
            CREATE OR REPLACE TABLE stg.nflverse_bulk_schedule_dictionary (
                field VARCHAR,
                data_type VARCHAR,
                description VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        con.executemany(
            '''
            INSERT INTO stg.nflverse_bulk_schedule_dictionary
              (field, data_type, description, _source_file_id, _adapter_id)
            VALUES (?, ?, ?, ?, ?)
            ''',
            [
                ('game_id', 'numeric', 'Game id', 'sf-1', 'nflverse_bulk'),
                ('week', 'numeric', 'Week', 'sf-1', 'nflverse_bulk'),
            ],
        )
    finally:
        con.close()

    result = execute_core_load(settings, adapter_id='nflverse_bulk', execute=True)
    assert result.mart_qualified_table == MART_SCHEDULE_FIELD_DICTIONARY_V1
    assert result.mart_row_count == 2

    con = duckdb.connect(str(settings.db_path))
    try:
        mart_rows = con.execute(
            f'SELECT field FROM {MART_SCHEDULE_FIELD_DICTIONARY_V1} ORDER BY field'
        ).fetchall()
    finally:
        con.close()
    assert [r[0] for r in mart_rows] == ['game_id', 'week']


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_parser_includes_mart_rebuild() -> None:
    parser = build_parser()
    args = parser.parse_args(['mart-rebuild'])
    assert args.command == 'mart-rebuild'
    assert args.mart_key == 'schedule_field_dictionary_v1'
    args = parser.parse_args(['mart-rebuild', '--mart-key', 'something_v2'])
    assert args.mart_key == 'something_v2'


def test_cli_mart_rebuild_succeeds(tmp_path, monkeypatch, capsys) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core(
        settings,
        [('week', 'numeric', 'Week number', 'sf-1', 'nflverse_bulk')],
    )
    monkeypatch.setattr(sys, 'argv', ['new-nfl', 'mart-rebuild'])
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert f'QUALIFIED_TABLE={MART_SCHEDULE_FIELD_DICTIONARY_V1}' in out
    assert 'ROW_COUNT=1' in out


# ---------------------------------------------------------------------------
# Lint: read modules MUST NOT touch core.* / stg.* / raw/ directly
# ---------------------------------------------------------------------------


def test_read_modules_do_not_reference_core_or_stg_directly() -> None:
    """Lint: read-path modules must not contain string literals that name
    ``core.*`` / ``stg.*`` / ``raw/`` — those are write-side schemas (ADR-0029).
    Docstrings are exempt; only inline string constants count as SQL/path use.
    """
    import ast

    repo_root = Path(__file__).resolve().parent.parent
    forbidden = ('core.', 'stg.', 'raw/')
    offenders: list[tuple[str, int, str]] = []
    for rel in READ_MODULES:
        path = repo_root / rel
        tree = ast.parse(path.read_text(encoding='utf-8'))
        # Collect docstring nodes to exempt them.
        doc_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body and isinstance(node.body[0], ast.Expr):
                    val = node.body[0].value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        doc_nodes.add(id(val))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in doc_nodes:
                    continue
                for token in forbidden:
                    if token in node.value:
                        offenders.append((rel, node.lineno, node.value.strip()[:120]))
                        break
    assert not offenders, (
        'read modules must read only from mart.*; offenders:\n'
        + '\n'.join(f'  {r}:{n}: {l}' for r, n, l in offenders)
    )
