"""Dedupe pipeline tests (T2.4B, ADR-0027)."""
from __future__ import annotations

import sys

import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli import build_parser, main
from new_nfl.dedupe import (
    NormalizedPlayer,
    RawPlayerRecord,
    RuleBasedPlayerScorer,
    build_blocks,
    cluster_pairs,
    normalize_player_record,
    open_review_items,
    run_player_dedupe,
)
from new_nfl.dedupe.pipeline import DEMO_PLAYER_RECORDS
from new_nfl.dedupe.score import score_pairs
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import load_settings


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def test_normalize_strips_diacritics_and_suffix():
    record = RawPlayerRecord(
        record_id='r1', full_name='Patrick  Mahômes II', position='qb', birth_year=1995
    )
    n = normalize_player_record(record)
    assert n.first_name == 'patrick'
    assert n.last_name == 'mahomes'
    assert n.suffix == 'ii'
    assert n.full_name_normalized == 'patrick mahomes'
    assert n.position_normalized == 'QB'
    assert n.first_initial == 'p'


def test_normalize_handles_single_token():
    record = RawPlayerRecord(record_id='r1', full_name='Pelé')
    n = normalize_player_record(record)
    assert n.last_name == 'pele'
    assert n.first_name == ''
    assert n.first_initial == ''


def test_block_groups_by_lastname_position_year():
    players = [
        normalize_player_record(r) for r in DEMO_PLAYER_RECORDS
    ]
    pairs = build_blocks(players)
    keys = {p.block_key for p in pairs}
    assert 'mahomes|QB|1995' in keys
    assert 'rodgers|QB|1983' in keys
    # Mahomes 1965 sits in its own bucket → no pair
    for pair in pairs:
        assert pair.left.record_id != pair.right.record_id


def test_block_drops_records_without_lastname():
    players = [
        normalize_player_record(RawPlayerRecord(record_id='r1', full_name='', position='QB')),
        normalize_player_record(RawPlayerRecord(record_id='r2', full_name='', position='QB')),
    ]
    assert build_blocks(players) == []


def test_rule_based_scorer_grades_match_levels():
    scorer = RuleBasedPlayerScorer()
    base = normalize_player_record(
        RawPlayerRecord(record_id='r1', full_name='Patrick Mahomes', position='QB', birth_year=1995)
    )
    twin = normalize_player_record(
        RawPlayerRecord(record_id='r2', full_name='Patrick Mahomes', position='QB', birth_year=1995)
    )
    initial = normalize_player_record(
        RawPlayerRecord(record_id='r3', full_name='P. Mahomes', position='QB', birth_year=1995)
    )
    distinct = normalize_player_record(
        RawPlayerRecord(record_id='r4', full_name='Aaron Rodgers', position='QB', birth_year=1983)
    )
    assert scorer.score(base, twin) >= 0.95
    assert 0.55 <= scorer.score(base, initial) <= 0.65
    assert scorer.score(base, distinct) == 0.0
    assert scorer.score(base, base) == 0.0


def test_cluster_pairs_unifies_above_upper_threshold_and_keeps_singletons():
    players = [
        NormalizedPlayer(
            record_id=f'r{i}', full_name='', full_name_normalized='', first_name='',
            last_name='x', first_initial='', position=None, position_normalized=None,
            birth_year=None, source_ref=None, extra_tokens=[],
        )
        for i in range(4)
    ]
    scored = score_pairs(
        build_blocks(players),
        scorer=type('S', (), {'kind': 'fake', 'score': lambda self, l, r: 0.9 if {l.record_id, r.record_id} == {'r0', 'r1'} else 0.0})(),
    )
    clusters = cluster_pairs(players, scored, upper_threshold=0.85)
    sizes = sorted(len(c.record_ids) for c in clusters)
    assert sizes == [1, 1, 2]


def test_run_player_dedupe_demo_produces_expected_buckets(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    result = run_player_dedupe(settings, records=list(DEMO_PLAYER_RECORDS))
    assert result.run_status == 'success'
    assert result.input_record_count == 6
    assert result.auto_merge_pair_count >= 1  # Mahomes 1995 twins
    assert result.review_pair_count >= 1  # A. Rodgers vs Aaron Rodgers
    # 6 inputs, with one auto-merge cluster ⇒ at most 5 clusters
    assert 1 <= result.cluster_count <= 5

    con = duckdb.connect(str(settings.db_path))
    try:
        run_count = con.execute(
            'SELECT COUNT(*) FROM meta.dedupe_run WHERE dedupe_run_id = ?',
            [result.dedupe_run_id],
        ).fetchone()[0]
        review_rows = con.execute(
            'SELECT COUNT(*) FROM meta.review_item WHERE dedupe_run_id = ?',
            [result.dedupe_run_id],
        ).fetchone()[0]
    finally:
        con.close()
    assert run_count == 1
    assert review_rows == result.review_pair_count


def test_open_review_items_returns_open_pairs(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    run_player_dedupe(settings, records=list(DEMO_PLAYER_RECORDS))
    open_items = open_review_items(settings, domain='players')
    assert len(open_items) >= 1
    for item in open_items:
        assert item['status'] == 'open'
        assert item['domain'] == 'players'


def test_meta_dedupe_tables_exist(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    ensure_metadata_surface(settings)
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'meta' AND table_name IN ('dedupe_run', 'review_item')
            ORDER BY table_name
            """
        ).fetchall()
    finally:
        con.close()
    assert [r[0] for r in rows] == ['dedupe_run', 'review_item']


def test_parser_registers_dedupe_commands():
    parser = build_parser()
    args = parser.parse_args(['dedupe-run', '--domain', 'players', '--demo'])
    assert args.command == 'dedupe-run'
    assert args.demo is True
    args = parser.parse_args(['dedupe-review-list'])
    assert args.command == 'dedupe-review-list'


def test_cli_dedupe_run_demo_smoke(tmp_path, monkeypatch, capsys):
    _bootstrap(tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys, 'argv', ['cli', 'dedupe-run', '--domain', 'players', '--demo']
    )
    assert main() == 0
    out = capsys.readouterr().out
    assert 'RUN_STATUS=success' in out
    assert 'CLUSTER_COUNT=' in out
    assert 'AUTO_MERGE_PAIR_COUNT=' in out

    monkeypatch.setattr(sys, 'argv', ['cli', 'dedupe-review-list', '--domain', 'players'])
    assert main() == 0
    out = capsys.readouterr().out
    assert 'OPEN_REVIEW_ITEM_COUNT=' in out


def test_cli_dedupe_run_rejects_unsupported_domain(tmp_path, monkeypatch, capsys):
    _bootstrap(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['cli', 'dedupe-run', '--domain', 'teams', '--demo'])
    assert main() == 2
    out = capsys.readouterr().out
    assert 'STATUS=unsupported_domain' in out


def test_cli_dedupe_run_requires_demo(tmp_path, monkeypatch, capsys):
    _bootstrap(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['cli', 'dedupe-run', '--domain', 'players'])
    assert main() == 2
    out = capsys.readouterr().out
    assert 'STATUS=missing_source' in out
