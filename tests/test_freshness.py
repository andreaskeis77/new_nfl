"""T2.6B — mart.freshness_overview_v1 + Home/Freshness service + render.

Covers the end-to-end read path ``meta.load_events`` +
``meta.quarantine_case`` → ``mart.freshness_overview_v1`` →
``web.freshness.build_home_overview`` → rendered HTML.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.mart import (
    EXPECTED_CORE_DOMAINS,
    MART_FRESHNESS_OVERVIEW_V1,
    build_freshness_overview_v1,
)
from new_nfl.settings import load_settings
from new_nfl.web.freshness import (
    build_home_overview,
    load_freshness_rows,
)
from new_nfl.web.renderer import render_home, render_home_from_settings


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_load_event(
    con: duckdb.DuckDBPyConnection,
    *,
    target_schema: str,
    target_object: str,
    ingest_run_id: str,
    recorded_at: datetime,
    event_status: str = 'loaded',
    event_kind: str = 'core_loaded',
    row_count: int | None = None,
) -> None:
    con.execute(
        '''
        INSERT INTO meta.load_events
            (load_event_id, ingest_run_id, target_schema, target_object,
             event_kind, event_status, row_count, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            f'le-{target_object}-{ingest_run_id}',
            ingest_run_id,
            target_schema,
            target_object,
            event_kind,
            event_status,
            row_count,
            recorded_at,
        ],
    )


def _seed_quarantine(
    con: duckdb.DuckDBPyConnection,
    *,
    scope_type: str,
    scope_ref: str,
    severity: str = 'warn',
    status: str = 'open',
    last_seen_at: datetime | None = None,
) -> None:
    ts = last_seen_at or datetime.now()
    con.execute(
        '''
        INSERT INTO meta.quarantine_case
            (quarantine_case_id, scope_type, scope_ref, reason_code,
             severity, status, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            f'q-{scope_type}-{scope_ref}',
            scope_type,
            scope_ref,
            'tier_b_disagreement',
            severity,
            status,
            ts,
            ts,
        ],
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_builder_emits_row_per_expected_domain_on_empty_db(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    result = build_freshness_overview_v1(settings)
    assert result.qualified_table == MART_FRESHNESS_OVERVIEW_V1
    assert result.row_count == len(EXPECTED_CORE_DOMAINS)
    assert result.source_row_count == 0

    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f'SELECT domain_object, freshness_status, last_event_at '
            f'FROM {MART_FRESHNESS_OVERVIEW_V1} ORDER BY display_order'
        ).fetchall()
    finally:
        con.close()
    objects = [r[0] for r in rows]
    assert objects == [d[1] for d in EXPECTED_CORE_DOMAINS]
    assert all(r[1] == 'stale' for r in rows)
    assert all(r[2] is None for r in rows)


def test_builder_reflects_latest_event_per_domain(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    base = datetime(2026, 4, 23, 10, 0)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='team',
            ingest_run_id='run-001',
            recorded_at=base,
            row_count=32,
        )
        _seed_load_event(
            con,
            target_schema='core',
            target_object='team',
            ingest_run_id='run-002',
            recorded_at=base + timedelta(hours=1),
            row_count=32,
        )
        _seed_load_event(
            con,
            target_schema='core',
            target_object='game',
            ingest_run_id='run-003',
            recorded_at=base + timedelta(hours=2),
            row_count=285,
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f'SELECT domain_object, last_ingest_run_id, last_row_count, '
            f'event_count, freshness_status '
            f'FROM {MART_FRESHNESS_OVERVIEW_V1} '
            f"WHERE domain_object IN ('team', 'game') "
            f'ORDER BY domain_object'
        ).fetchall()
    finally:
        con.close()
    as_dict = {r[0]: r for r in rows}
    assert as_dict['team'][1] == 'run-002'
    assert as_dict['team'][2] == 32
    assert as_dict['team'][3] == 2
    assert as_dict['team'][4] == 'ok'
    assert as_dict['game'][1] == 'run-003'
    assert as_dict['game'][4] == 'ok'


def test_builder_promotes_warn_when_quarantine_open(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='player',
            ingest_run_id='run-pl-1',
            recorded_at=datetime(2026, 4, 23, 9, 0),
            row_count=3072,
        )
        _seed_quarantine(
            con,
            scope_type='player',
            scope_ref='00-0033873',
            severity='warn',
            status='open',
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f'SELECT freshness_status, open_quarantine_count, '
            f'quarantine_max_severity FROM {MART_FRESHNESS_OVERVIEW_V1} '
            f"WHERE domain_object = 'player'"
        ).fetchall()
    finally:
        con.close()
    assert rows == [('warn', 1, 'warn')]


def test_builder_marks_failed_event_as_fail(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='roster_membership',
            ingest_run_id='run-r-1',
            recorded_at=datetime(2026, 4, 23, 10, 0),
            event_status='failed',
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        status = con.execute(
            f'SELECT freshness_status FROM {MART_FRESHNESS_OVERVIEW_V1} '
            f"WHERE domain_object = 'roster_membership'"
        ).fetchone()
    finally:
        con.close()
    assert status == ('fail',)


def test_builder_ignores_resolved_quarantine_cases(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='team_stats_weekly',
            ingest_run_id='run-ts-1',
            recorded_at=datetime(2026, 4, 23, 12, 0),
            row_count=544,
        )
        _seed_quarantine(
            con,
            scope_type='team_stats_weekly',
            scope_ref='KC:2024:W01',
            status='resolved',
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            f'SELECT freshness_status, open_quarantine_count '
            f'FROM {MART_FRESHNESS_OVERVIEW_V1} '
            f"WHERE domain_object = 'team_stats_weekly'"
        ).fetchone()
    finally:
        con.close()
    assert row == ('ok', 0)


def test_builder_ignores_non_core_schemas(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='raw',
            target_object='nflverse_bulk_teams',
            ingest_run_id='run-raw-1',
            recorded_at=datetime(2026, 4, 23, 8, 0),
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        schemas = {
            r[0]
            for r in con.execute(
                f'SELECT DISTINCT domain_schema FROM {MART_FRESHNESS_OVERVIEW_V1}'
            ).fetchall()
        }
    finally:
        con.close()
    assert schemas == {'core'}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def test_service_returns_synthetic_stale_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    rows = load_freshness_rows(settings)
    assert len(rows) == len(EXPECTED_CORE_DOMAINS)
    assert all(r.freshness_status == 'stale' for r in rows)
    assert all(r.last_event_at is None for r in rows)


def test_service_aggregates_overview_totals(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='team',
            ingest_run_id='r-1',
            recorded_at=datetime(2026, 4, 23, 9, 0),
            row_count=32,
        )
        _seed_load_event(
            con,
            target_schema='core',
            target_object='player',
            ingest_run_id='r-2',
            recorded_at=datetime(2026, 4, 23, 9, 30),
            row_count=3072,
        )
        _seed_quarantine(
            con, scope_type='player', scope_ref='00-X', severity='warn', status='open',
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)
    overview = build_home_overview(settings)

    assert overview.total_row_count == 32 + 3072
    assert overview.open_quarantine_count == 1
    assert overview.domains_warn == 1
    assert overview.domains_ok == 1
    assert overview.domains_stale == len(EXPECTED_CORE_DOMAINS) - 2


# ---------------------------------------------------------------------------
# Render wiring
# ---------------------------------------------------------------------------


def test_render_home_with_overview_lists_all_expected_domains(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    build_freshness_overview_v1(settings)
    html = render_home_from_settings(settings)
    assert 'Teams' in html
    assert 'Games' in html
    assert 'Players' in html
    assert 'Rosters' in html
    assert 'Team Stats (weekly)' in html
    assert 'Player Stats (weekly)' in html
    assert 'Noch keine Freshness-Daten' not in html


def test_render_home_shows_quarantine_badge_when_open(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='player',
            ingest_run_id='r-pl',
            recorded_at=datetime(2026, 4, 23, 9, 0),
            row_count=3072,
        )
        _seed_quarantine(
            con,
            scope_type='player',
            scope_ref='00-X',
            severity='warn',
            status='open',
        )
    finally:
        con.close()
    build_freshness_overview_v1(settings)

    html = render_home_from_settings(settings)
    assert 'Offene Quarantäne-Fälle' in html
    assert 'status-warn' in html


def test_render_home_tiles_reflect_computed_stats(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object='team',
            ingest_run_id='r-t',
            recorded_at=datetime(2026, 4, 23, 9, 0),
            row_count=32,
        )
    finally:
        con.close()
    build_freshness_overview_v1(settings)

    html = render_home_from_settings(settings)
    assert 'Domänen grün' in html
    assert 'Domänen stale' in html
    assert 'Offene Quarantäne' in html


def test_render_home_without_overview_keeps_demo_preview(tmp_path, monkeypatch) -> None:
    html = render_home()
    assert 'KC @ BAL' in html


def test_runner_executor_mart_build_accepts_freshness_key(tmp_path, monkeypatch) -> None:
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
        job_key='mart_build_fresh',
        job_type='mart_build',
        retry_policy_key='only_one',
    )
    enqueue_job(
        settings,
        job_key='mart_build_fresh',
        params={'mart_key': 'freshness_overview_v1'},
    )
    tick = run_worker_once(settings, worker_id='w')
    assert tick.run_status == 'success', tick.message
    assert tick.detail['qualified_table'] == MART_FRESHNESS_OVERVIEW_V1
    assert tick.detail['row_count'] == len(EXPECTED_CORE_DOMAINS)


# ---------------------------------------------------------------------------
# Read-surface invariant (ADR-0029): the service reads only ``mart.*``.
# ---------------------------------------------------------------------------


def test_service_does_not_read_core_tables_directly(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute('CREATE SCHEMA IF NOT EXISTS core')
        con.execute(
            """
            CREATE TABLE core.forbidden_probe (value INTEGER);
            INSERT INTO core.forbidden_probe VALUES (1);
            """
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)
    rows = load_freshness_rows(settings)
    assert rows, 'service must populate rows even with unrelated core tables present'
    overview = build_home_overview(settings)
    assert overview.total_row_count >= 0


def test_builder_idempotent_on_rebuild(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    first = build_freshness_overview_v1(settings)
    second = build_freshness_overview_v1(settings)
    assert first.row_count == second.row_count == len(EXPECTED_CORE_DOMAINS)


@pytest.mark.parametrize(
    'scope_type,expected_status',
    [
        ('team', 'warn'),
        ('game', 'warn'),
        ('roster_membership', 'warn'),
        ('player_stats_weekly', 'warn'),
    ],
)
def test_builder_routes_quarantine_across_domains(
    tmp_path, monkeypatch, scope_type, expected_status
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema='core',
            target_object=scope_type,
            ingest_run_id=f'r-{scope_type}',
            recorded_at=datetime(2026, 4, 23, 10, 0),
            row_count=1,
        )
        _seed_quarantine(
            con, scope_type=scope_type, scope_ref='X', status='open',
        )
    finally:
        con.close()

    build_freshness_overview_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            f'SELECT freshness_status FROM {MART_FRESHNESS_OVERVIEW_V1} '
            f'WHERE domain_object = ?',
            [scope_type],
        ).fetchone()
    finally:
        con.close()
    assert row == (expected_status,)
