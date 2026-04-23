"""Tests for ``replay_domain`` (T2.7D).

Uses the ``team`` domain as the smallest deterministic fixture: a handful
of Tier-A rows promoted into ``core.team`` via the real
``execute_core_team_load`` loader. The replay drill must produce an empty
diff (excluding timestamp columns) — a non-empty diff is a determinism
bug in the core-load and the test will surface it.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from new_nfl.adapters.slices import get_slice
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.core.teams import CORE_TEAM_TABLE, execute_core_team_load
from new_nfl.metadata import seed_default_sources
from new_nfl.resilience.replay import DOMAIN_SPECS, replay_domain
from new_nfl.settings import Settings


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    db_path = data_root / "db" / "new_nfl.duckdb"
    repo_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        repo_root=repo_root,
        env="test",
        data_root=data_root,
        db_path=db_path,
    )


_TIER_A_ROWS: tuple[tuple, ...] = (
    ("KC", "KC", "Kansas City Chiefs", "Chiefs", "AFC", "AFC West",
     "#E31837", "#FFB81C", "1960", None, None),
    ("SF", "SF", "San Francisco 49ers", "49ers", "NFC", "NFC West",
     "#AA0000", "#B3995D", "1946", None, None),
)


def _seed_tier_a_stage(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)
    primary = get_slice("nflverse_bulk", "teams")
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS stg")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {primary.stage_qualified_table} (
                team_id VARCHAR,
                team_abbr VARCHAR,
                team_name VARCHAR,
                team_nick VARCHAR,
                team_conference VARCHAR,
                team_division VARCHAR,
                team_color VARCHAR,
                team_color2 VARCHAR,
                first_season VARCHAR,
                last_season VARCHAR,
                successor_team_id VARCHAR,
                _source_file_id VARCHAR,
                _adapter_id VARCHAR,
                _loaded_at TIMESTAMP
            )
            """
        )
        for row in _TIER_A_ROWS:
            con.execute(
                f"""
                INSERT INTO {primary.stage_qualified_table} (
                    team_id, team_abbr, team_name, team_nick,
                    team_conference, team_division, team_color, team_color2,
                    first_season, last_season, successor_team_id,
                    _source_file_id, _adapter_id, _loaded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [*row, "sf-a-1", primary.adapter_id],
            )
    finally:
        con.close()


def _prime_core_team(settings: Settings) -> None:
    _seed_tier_a_stage(settings)
    execute_core_team_load(settings, execute=True)


# ---------------------------------------------------------------------------
# Domain registry sanity
# ---------------------------------------------------------------------------


def test_domain_registry_covers_all_expected_domains() -> None:
    expected = {
        "team", "game", "player", "roster_membership",
        "team_stats_weekly", "player_stats_weekly",
    }
    assert set(DOMAIN_SPECS) == expected


def test_domain_spec_key_cols_are_non_empty_tuples() -> None:
    for spec in DOMAIN_SPECS.values():
        assert isinstance(spec.key_cols, tuple)
        assert spec.key_cols, f"empty key_cols for {spec.domain}"


def test_replay_unknown_domain_raises(settings: Settings) -> None:
    with pytest.raises(ValueError, match="unknown domain"):
        replay_domain(settings, domain="not_a_domain")


# ---------------------------------------------------------------------------
# Dry-run path
# ---------------------------------------------------------------------------


def test_replay_dry_run_reports_row_count_without_mutating(
    settings: Settings,
) -> None:
    _prime_core_team(settings)

    # Snapshot pre-state row count.
    con = duckdb.connect(str(settings.db_path))
    try:
        pre = int(con.execute(f"SELECT COUNT(*) FROM {CORE_TEAM_TABLE}").fetchone()[0])
    finally:
        con.close()

    result = replay_domain(settings, domain="team", dry_run=True)
    assert result.dry_run is True
    assert result.diff is None
    assert result.pre_row_count == pre
    assert result.post_row_count == pre
    assert result.loader_result is None
    assert any("dry_run" in note for note in result.notes)

    # Verify nothing changed in the live DB.
    con = duckdb.connect(str(settings.db_path))
    try:
        post = int(con.execute(f"SELECT COUNT(*) FROM {CORE_TEAM_TABLE}").fetchone()[0])
    finally:
        con.close()
    assert pre == post


# ---------------------------------------------------------------------------
# Happy path — replay yields empty diff on identical raw input.
# ---------------------------------------------------------------------------


def test_replay_on_unchanged_raw_has_empty_diff(
    settings: Settings,
) -> None:
    """The core contract: re-running core-load on unchanged raw is deterministic.

    If this ever starts to fail, do NOT weaken the test — it means a
    core-load promoter is no longer idempotent (e.g., emitting
    non-deterministic tie-breaks or timestamps outside the default
    exclude list). That is a blocking defect for the resilience drill.
    """
    _prime_core_team(settings)

    result = replay_domain(
        settings,
        domain="team",
        source_file_id="sf-a-1",
    )
    assert result.dry_run is False
    assert result.diff is not None, "replay must return a diff in non-dry-run"
    assert result.is_deterministic, (
        f"replay-diff not empty: {result.diff.summary()} "
        f"only_in_a={list(result.diff.only_in_a)} "
        f"only_in_b={list(result.diff.only_in_b)} "
        f"changed={list(result.diff.changed)}"
    )
    assert result.pre_row_count == len(_TIER_A_ROWS)
    assert result.post_row_count == len(_TIER_A_ROWS)
    assert result.source_file_id == "sf-a-1"


def test_replay_without_prior_core_load_raises(settings: Settings) -> None:
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    with pytest.raises(ValueError, match="does not exist"):
        replay_domain(settings, domain="team")
