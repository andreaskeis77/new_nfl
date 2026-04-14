from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import new_nfl.cli as cli_module
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import seed_default_sources
from new_nfl.settings import Settings


def test_build_parser_accepts_describe_core_field_command() -> None:
    parser = cli_module.build_parser()

    args = parser.parse_args(
        ['describe-core-field', '--adapter-id', 'nflverse_bulk', '--field', 'game_id']
    )

    assert args.command == 'describe-core-field'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.field == 'game_id'


def test_build_parser_requires_field_for_describe_core_field() -> None:
    parser = cli_module.build_parser()

    try:
        parser.parse_args(['describe-core-field', '--adapter-id', 'nflverse_bulk'])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError('expected parser to reject missing --field')


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    repo_root = tmp_path / 'repo'
    data_root = repo_root / 'data'
    db_path = data_root / 'db' / 'new_nfl.duckdb'
    repo_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        repo_root=repo_root,
        env='test',
        data_root=data_root,
        db_path=db_path,
    )


def _prepare_core_table(settings: Settings) -> None:
    from new_nfl.mart import build_schedule_field_dictionary_v1

    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS core')
        con.execute(
            '''
            CREATE OR REPLACE TABLE core.schedule_field_dictionary (
                field VARCHAR,
                data_type VARCHAR,
                description VARCHAR,
                _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        con.execute(
            '''
            INSERT INTO core.schedule_field_dictionary (field, data_type, description)
            VALUES
                ('game_id', 'numeric', 'Primary game identifier'),
                ('game_type', 'character', 'Game type'),
                ('gameday', 'character', 'Game date'),
                ('gametime', 'character', 'Kickoff time'),
                ('home_team', 'character', 'Home team code')
            '''
        )
    finally:
        con.close()
    build_schedule_field_dictionary_v1(settings)


def test_cmd_describe_core_field_returns_zero_for_hit(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare_core_table(settings)
    monkeypatch.setattr(cli_module, 'load_settings', lambda: settings)

    exit_code = cli_module._cmd_describe_core_field('nflverse_bulk', 'game_id')
    out = capsys.readouterr().out

    assert exit_code == 0
    assert 'FOUND=yes' in out
    assert 'FIELD=game_id' in out
    assert 'MISS_REASON=' not in out


def test_cmd_describe_core_field_returns_one_and_suggestions_for_miss(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare_core_table(settings)
    monkeypatch.setattr(cli_module, 'load_settings', lambda: settings)

    exit_code = cli_module._cmd_describe_core_field('nflverse_bulk', 'game')
    out = capsys.readouterr().out

    assert exit_code == 1
    assert 'FOUND=no' in out
    assert 'MISS_REASON=field_not_found' in out
    assert 'SUGGESTION_COUNT=4' in out
    assert 'SUGGESTION=game_id' in out
    assert 'SUGGESTION=game_type' in out
