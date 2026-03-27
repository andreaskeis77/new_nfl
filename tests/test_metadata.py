import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import (
    finish_ingest_run,
    list_sources,
    record_dq_event,
    record_load_event,
    seed_default_sources,
    start_ingest_run,
    upsert_pipeline_state,
)
from new_nfl.settings import load_settings


def test_seed_default_sources_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)

    first_seed = seed_default_sources(settings)
    second_seed = seed_default_sources(settings)
    rows = list_sources(settings)

    assert first_seed == 4
    assert second_seed == 4
    assert len(rows) == 4
    assert rows[0]['source_id'] == 'nflverse_bulk'


def test_pipeline_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)

    upsert_pipeline_state(
        settings,
        pipeline_name='bootstrap_local',
        last_run_status='success',
        state_json='{"phase":"T1.1"}',
        mark_success=True,
    )

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            """
            SELECT pipeline_name, last_run_status, state_json
            FROM meta.pipeline_state
            WHERE pipeline_name = 'bootstrap_local'
            """
        ).fetchone()
    finally:
        con.close()

    assert row == ('bootstrap_local', 'success', '{"phase":"T1.1"}')


def test_ingest_run_event_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    ingest_run_id = start_ingest_run(
        settings,
        pipeline_name='seed_registry',
        triggered_by='pytest',
        run_mode='test',
        detail_json='{"scope":"registry"}',
    )
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id='nflverse_bulk',
        target_schema='meta',
        target_object='source_registry',
        row_count=4,
        event_status='loaded',
        detail_json='{"seeded":true}',
    )
    dq_event_id = record_dq_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id='nflverse_bulk',
        severity='info',
        dq_rule_code='registry_seed_complete',
        target_schema='meta',
        target_object='source_registry',
        affected_row_count=0,
        detail_json='{"status":"clean"}',
    )
    finish_ingest_run(
        settings,
        ingest_run_id=ingest_run_id,
        run_status='success',
        detail_json='{"final":"ok"}',
    )

    con = duckdb.connect(str(settings.db_path))
    try:
        run_row = con.execute(
            "SELECT run_status FROM meta.ingest_runs WHERE ingest_run_id = ?",
            [ingest_run_id],
        ).fetchone()
        load_row = con.execute(
            "SELECT event_status FROM meta.load_events WHERE load_event_id = ?",
            [load_event_id],
        ).fetchone()
        dq_row = con.execute(
            "SELECT severity FROM meta.dq_events WHERE dq_event_id = ?",
            [dq_event_id],
        ).fetchone()
    finally:
        con.close()

    assert run_row == ('success',)
    assert load_row == ('loaded',)
    assert dq_row == ('info',)
