"""Ontology-as-Code tests (T2.4A, ADR-0026)."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli import build_parser, main
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.ontology import describe_term, list_terms, load_ontology_directory
from new_nfl.settings import load_settings


ONTOLOGY_SEED_DIR = Path(__file__).resolve().parent.parent / 'ontology' / 'v0_1'


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def test_meta_ontology_tables_exist(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    ensure_metadata_surface(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'meta' AND table_name LIKE 'ontology_%'
            ORDER BY table_name
            """
        ).fetchall()
    finally:
        con.close()
    names = [r[0] for r in rows]
    assert names == [
        'ontology_alias',
        'ontology_mapping',
        'ontology_term',
        'ontology_value_set',
        'ontology_value_set_member',
        'ontology_version',
    ]


def test_load_ontology_directory_inserts_all_rows(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    result = load_ontology_directory(
        settings, source_dir=ONTOLOGY_SEED_DIR, version_label='v0_1'
    )
    assert result.is_new is True
    assert result.file_count == 3
    assert result.term_count == 3
    assert result.alias_count >= 8
    assert result.value_set_count >= 4
    assert result.value_set_member_count >= 25

    con = duckdb.connect(str(settings.db_path))
    try:
        assert con.execute(
            'SELECT COUNT(*) FROM meta.ontology_version WHERE is_active = TRUE'
        ).fetchone()[0] == 1
        assert con.execute(
            'SELECT COUNT(*) FROM meta.ontology_term'
        ).fetchone()[0] == 3
    finally:
        con.close()


def test_load_ontology_directory_is_idempotent(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    first = load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)
    second = load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)
    assert first.ontology_version_id == second.ontology_version_id
    assert first.content_sha256 == second.content_sha256
    assert second.is_new is False

    con = duckdb.connect(str(settings.db_path))
    try:
        version_count = con.execute(
            'SELECT COUNT(*) FROM meta.ontology_version'
        ).fetchone()[0]
        term_count = con.execute(
            'SELECT COUNT(*) FROM meta.ontology_term'
        ).fetchone()[0]
    finally:
        con.close()
    assert version_count == 1
    assert term_count == 3


def test_new_content_creates_new_version_and_activates(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)

    alt_dir = tmp_path / 'ontology_alt'
    alt_dir.mkdir()
    (alt_dir / 'term_position.toml').write_text(
        (ONTOLOGY_SEED_DIR / 'term_position.toml').read_text(encoding='utf-8'),
        encoding='utf-8',
    )

    second = load_ontology_directory(settings, source_dir=alt_dir, version_label='alt')
    assert second.is_new is True

    con = duckdb.connect(str(settings.db_path))
    try:
        active_rows = con.execute(
            'SELECT ontology_version_id, source_dir FROM meta.ontology_version WHERE is_active = TRUE'
        ).fetchall()
    finally:
        con.close()
    assert len(active_rows) == 2
    source_dirs = {row[1] for row in active_rows}
    assert str(ONTOLOGY_SEED_DIR.resolve()) in source_dirs


def test_describe_term_returns_term_and_value_sets(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)

    detail = describe_term(settings, 'position')
    assert detail is not None
    assert detail.term_key == 'position'
    vs_keys = {vs.value_set_key for vs in detail.value_sets}
    assert {'all_positions', 'offense_positions'}.issubset(vs_keys)

    all_positions = next(vs for vs in detail.value_sets if vs.value_set_key == 'all_positions')
    values = {m.value for m in all_positions.members}
    assert {'QB', 'RB', 'WR', 'TE', 'K'}.issubset(values)


def test_describe_term_resolves_alias(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)
    detail = describe_term(settings, 'pos')
    assert detail is not None
    assert detail.term_key == 'position'


def test_describe_term_returns_none_for_unknown(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)
    assert describe_term(settings, 'not_a_term') is None


def test_list_terms_returns_all_active_terms(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    load_ontology_directory(settings, source_dir=ONTOLOGY_SEED_DIR)
    terms = list_terms(settings)
    keys = {t.term_key for t in terms}
    assert keys == {'position', 'game_status', 'injury_status'}


def test_empty_source_dir_rejected(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    empty_dir = tmp_path / 'empty_ontology'
    empty_dir.mkdir()
    with pytest.raises(ValueError):
        load_ontology_directory(settings, source_dir=empty_dir)


def test_parser_registers_ontology_commands():
    parser = build_parser()
    for name in ('ontology-load', 'ontology-list', 'ontology-show'):
        args = parser.parse_args([name, '--source-dir', 'x']
                                 if name == 'ontology-load'
                                 else [name, '--term-key', 'position']
                                 if name == 'ontology-show'
                                 else [name])
        assert args.command == name


def test_cli_ontology_load_and_show(tmp_path, monkeypatch, capsys):
    _bootstrap(tmp_path, monkeypatch)
    rc = main.__wrapped__() if hasattr(main, '__wrapped__') else None  # noqa: F841
    # Load
    monkeypatch.setattr(
        sys,
        'argv',
        ['cli', 'ontology-load', '--source-dir', str(ONTOLOGY_SEED_DIR), '--version-label', 'v0_1'],
    )
    assert main() == 0
    out = capsys.readouterr().out
    assert 'TERM_COUNT=3' in out
    assert 'IS_NEW=yes' in out

    # Show
    monkeypatch.setattr(sys, 'argv', ['cli', 'ontology-show', '--term-key', 'game_status'])
    assert main() == 0
    out = capsys.readouterr().out
    assert 'FOUND=yes' in out
    assert 'TERM_KEY=game_status' in out
    assert 'VALUE_SET=all_game_statuses' in out

    # Unknown
    monkeypatch.setattr(sys, 'argv', ['cli', 'ontology-show', '--term-key', 'nope'])
    assert main() == 1
    out = capsys.readouterr().out
    assert 'FOUND=no' in out

    # List
    monkeypatch.setattr(sys, 'argv', ['cli', 'ontology-list'])
    assert main() == 0
    out = capsys.readouterr().out
    assert 'TERM_COUNT=3' in out
