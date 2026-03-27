import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import (
    get_pipeline_state,
    list_sources,
    seed_default_sources,
    upsert_pipeline_state,
)
from new_nfl.settings import load_settings


LEGACY_SOURCE_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS meta.source_registry (
    source_key VARCHAR PRIMARY KEY,
    source_name VARCHAR NOT NULL,
    source_tier VARCHAR NOT NULL,
    source_priority INTEGER NOT NULL,
    source_kind VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    update_frequency VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

LEGACY_PIPELINE_STATE_DDL = """
CREATE TABLE IF NOT EXISTS meta.pipeline_state (
    pipeline_key VARCHAR PRIMARY KEY,
    last_successful_run_at TIMESTAMP,
    last_attempted_run_at TIMESTAMP,
    last_run_status VARCHAR,
    details_json VARCHAR
)
"""


def _prepare_legacy_db(settings):
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        con.execute(LEGACY_SOURCE_REGISTRY_DDL)
        con.execute(LEGACY_PIPELINE_STATE_DDL)
    finally:
        con.close()


def test_seed_default_sources_migrates_legacy_source_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    _prepare_legacy_db(settings)

    bootstrap_local_environment(settings)
    seeded = seed_default_sources(settings)
    rows = list_sources(settings)

    assert seeded == 4
    assert len(rows) == 4
    assert rows[0]["source_id"] == "nflverse_bulk"

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            (
                "SELECT source_key, source_id "
                "FROM meta.source_registry "
                "WHERE source_key = 'nflverse_bulk'"
            )
        ).fetchone()
    finally:
        con.close()

    assert row == ("nflverse_bulk", "nflverse_bulk")


def test_pipeline_state_upsert_supports_legacy_table(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    _prepare_legacy_db(settings)

    bootstrap_local_environment(settings)
    upsert_pipeline_state(
        settings,
        pipeline_name="bootstrap_local",
        last_run_status="success",
        state_json='{"phase":"T1.1A"}',
        mark_success=True,
    )
    state = get_pipeline_state(settings, "bootstrap_local")

    assert state is not None
    assert state["pipeline_name"] == "bootstrap_local"
    assert state["last_run_status"] == "success"
    assert state["state_json"] == '{"phase":"T1.1A"}'

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            (
                "SELECT pipeline_key, pipeline_name "
                "FROM meta.pipeline_state "
                "WHERE pipeline_key = 'bootstrap_local'"
            )
        ).fetchone()
    finally:
        con.close()

    assert row == ("bootstrap_local", "bootstrap_local")
