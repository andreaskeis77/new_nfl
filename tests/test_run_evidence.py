"""Run-Evidence-Browser tests (T2.6H, ADR-0029).

Covers the three run-evidence marts (``mart.run_overview_v1``,
``mart.run_event_v1``, ``mart.run_artifact_v1``), the read service
(``list_runs``, ``get_run_detail``) and the two rendered pages
(``/runs``, ``/runs/<job_run_id>``).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.mart import (
    MART_RUN_ARTIFACT_V1,
    MART_RUN_EVENT_V1,
    MART_RUN_OVERVIEW_V1,
    build_run_evidence_v1,
)
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import load_settings
from new_nfl.web import (
    RunDetail,
    RunListPage,
    RunSummary,
    get_run_detail,
    list_runs,
    render_run_detail_page,
    render_runs_page,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv('NEW_NFL_REPO_ROOT', str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    ensure_metadata_surface(settings)
    return settings


def _seed_job_definition(con, *, job_id: str, job_key: str, job_type: str) -> None:
    con.execute(
        """
        INSERT INTO meta.job_definition (job_id, job_key, job_type)
        VALUES (?, ?, ?)
        """,
        [job_id, job_key, job_type],
    )


def _seed_job_run(
    con,
    *,
    job_run_id: str,
    job_id: str,
    run_status: str,
    started_at: datetime,
    finished_at: datetime | None,
    attempt_number: int = 1,
    worker_id: str | None = 'w-1',
    message: str | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO meta.job_run
            (job_run_id, job_id, queue_item_id, run_status, attempt_number,
             worker_id, message, detail_json, started_at, finished_at)
        VALUES (?, ?, NULL, ?, ?, ?, ?, '{}', ?, ?)
        """,
        [
            job_run_id, job_id, run_status, attempt_number, worker_id,
            message, started_at, finished_at,
        ],
    )


def _seed_run_event(
    con,
    *,
    run_event_id: str,
    job_run_id: str,
    event_kind: str,
    severity: str | None,
    recorded_at: datetime,
    message: str | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO meta.run_event
            (run_event_id, job_run_id, event_kind, severity, message,
             detail_json, recorded_at)
        VALUES (?, ?, ?, ?, ?, '{}', ?)
        """,
        [run_event_id, job_run_id, event_kind, severity, message, recorded_at],
    )


def _seed_run_artifact(
    con,
    *,
    run_artifact_id: str,
    job_run_id: str,
    artifact_kind: str,
    ref_id: str | None = None,
    ref_path: str | None = None,
    recorded_at: datetime | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO meta.run_artifact
            (run_artifact_id, job_run_id, artifact_kind, ref_id, ref_path,
             detail_json, recorded_at)
        VALUES (?, ?, ?, ?, ?, '{}', ?)
        """,
        [run_artifact_id, job_run_id, artifact_kind, ref_id, ref_path,
         recorded_at or datetime(2024, 9, 15, 10, 0, 0)],
    )


def _seed_happy_runset(con) -> None:
    """Three runs covering all UX branches.

    - run-A: success, 2 events (1 info, 1 warn), 1 artifact, 42 seconds
    - run-B: failed, 3 events (2 errors), 0 artifacts, 5 seconds
    - run-C: running, no finished_at, 1 event, 0 artifacts
    """
    _seed_job_definition(con, job_id='j-1', job_key='fetch_nflverse', job_type='fetch_remote')
    _seed_job_definition(con, job_id='j-2', job_key='stage_nflverse', job_type='stage_load')

    base = datetime(2024, 9, 15, 10, 0, 0)
    _seed_job_run(
        con,
        job_run_id='run-A',
        job_id='j-1',
        run_status='success',
        started_at=base,
        finished_at=base + timedelta(seconds=42),
        message='ok',
    )
    _seed_job_run(
        con,
        job_run_id='run-B',
        job_id='j-2',
        run_status='failed',
        started_at=base + timedelta(minutes=10),
        finished_at=base + timedelta(minutes=10, seconds=5),
        attempt_number=3,
        message='http 500',
    )
    _seed_job_run(
        con,
        job_run_id='run-C',
        job_id='j-1',
        run_status='running',
        started_at=base + timedelta(minutes=20),
        finished_at=None,
    )

    _seed_run_event(
        con,
        run_event_id='ev-A1',
        job_run_id='run-A',
        event_kind='executor_started',
        severity='info',
        recorded_at=base + timedelta(seconds=1),
    )
    _seed_run_event(
        con,
        run_event_id='ev-A2',
        job_run_id='run-A',
        event_kind='rows_written',
        severity='warn',
        recorded_at=base + timedelta(seconds=30),
        message='slow batch',
    )
    _seed_run_event(
        con,
        run_event_id='ev-B1',
        job_run_id='run-B',
        event_kind='executor_failed',
        severity='error',
        recorded_at=base + timedelta(minutes=10, seconds=3),
        message='http 500',
    )
    _seed_run_event(
        con,
        run_event_id='ev-B2',
        job_run_id='run-B',
        event_kind='executor_failed',
        severity='error',
        recorded_at=base + timedelta(minutes=10, seconds=4),
    )
    _seed_run_event(
        con,
        run_event_id='ev-B3',
        job_run_id='run-B',
        event_kind='runner_exhausted',
        severity='critical',
        recorded_at=base + timedelta(minutes=10, seconds=5),
    )
    _seed_run_event(
        con,
        run_event_id='ev-C1',
        job_run_id='run-C',
        event_kind='executor_started',
        severity='info',
        recorded_at=base + timedelta(minutes=20, seconds=1),
    )

    _seed_run_artifact(
        con,
        run_artifact_id='art-A1',
        job_run_id='run-A',
        artifact_kind='source_file',
        ref_id='sf-001',
        ref_path='raw/nflverse_bulk/sf-001.csv',
        recorded_at=base + timedelta(seconds=41),
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_build_run_evidence_v1_empty_environment(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    result = build_run_evidence_v1(settings)
    assert result.qualified_table == MART_RUN_OVERVIEW_V1
    assert result.row_count == 0
    assert result.event_row_count == 0
    assert result.artifact_row_count == 0


def test_build_run_evidence_v1_projects_runs_with_aggregates(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()

    result = build_run_evidence_v1(settings)
    assert result.row_count == 3
    assert result.event_row_count == 6
    assert result.artifact_row_count == 1

    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(
            f"""
            SELECT job_run_id, job_key, job_type, run_status,
                   duration_seconds, event_count, error_event_count,
                   warn_event_count, artifact_count
            FROM {MART_RUN_OVERVIEW_V1}
            ORDER BY job_run_id
            """
        ).fetchall()
    finally:
        con.close()

    by_id = {r[0]: r for r in rows}
    assert by_id['run-A'][1] == 'fetch_nflverse'
    assert by_id['run-A'][2] == 'fetch_remote'
    assert by_id['run-A'][3] == 'success'
    assert by_id['run-A'][4] == pytest.approx(42.0)
    assert by_id['run-A'][5] == 2
    assert by_id['run-A'][6] == 0
    assert by_id['run-A'][7] == 1
    assert by_id['run-A'][8] == 1

    assert by_id['run-B'][3] == 'failed'
    assert by_id['run-B'][5] == 3
    assert by_id['run-B'][6] == 3
    assert by_id['run-B'][7] == 0
    assert by_id['run-B'][8] == 0

    assert by_id['run-C'][3] == 'running'
    assert by_id['run-C'][4] is None


def test_build_run_evidence_v1_is_idempotent_on_rebuild(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    first = build_run_evidence_v1(settings)
    second = build_run_evidence_v1(settings)
    assert first.row_count == second.row_count == 3
    assert first.event_row_count == second.event_row_count == 6


# ---------------------------------------------------------------------------
# Service — list_runs
# ---------------------------------------------------------------------------


def test_list_runs_empty_when_mart_missing(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    page = list_runs(settings)
    assert isinstance(page, RunListPage)
    assert page.rows == ()
    assert page.total == 0


def test_list_runs_orders_newest_first(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    page = list_runs(settings)
    assert page.total == 3
    ids = [r.job_run_id for r in page.rows]
    assert ids == ['run-C', 'run-B', 'run-A']


def test_list_runs_filters_by_status_case_insensitive(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    page = list_runs(settings, status='FAILED')
    assert page.total == 1
    assert page.rows[0].job_run_id == 'run-B'
    assert page.status_filter == 'FAILED'


def test_list_runs_pagination_bundle(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    page = list_runs(settings, offset=0, limit=2)
    assert len(page.rows) == 2
    assert page.has_prev is False
    assert page.has_next is True
    assert page.next_offset == 2
    assert page.page_range_label == '1–2 von 3'

    page2 = list_runs(settings, offset=2, limit=2)
    assert len(page2.rows) == 1
    assert page2.has_prev is True
    assert page2.has_next is False


def test_run_summary_duration_label_formats(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    page = list_runs(settings)
    by_id = {r.job_run_id: r for r in page.rows}
    assert by_id['run-A'].duration_label == '42s'
    assert by_id['run-B'].duration_label == '5s'
    assert by_id['run-C'].duration_label == '—'


def test_run_summary_status_label_maps_to_de(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    page = list_runs(settings)
    by_id = {r.job_run_id: r for r in page.rows}
    assert by_id['run-A'].status_label == 'OK'
    assert by_id['run-B'].status_label == 'Fehlgeschlagen'
    assert by_id['run-C'].status_label == 'Läuft'


def test_run_summary_evidence_label_surfaces_errors(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    page = list_runs(settings)
    by_id = {r.job_run_id: r for r in page.rows}
    label_b = by_id['run-B'].evidence_label
    assert '3 Events' in label_b
    assert '3 err' in label_b
    assert '0 Artefakte' in label_b
    label_a = by_id['run-A'].evidence_label
    assert '1 warn' in label_a
    assert '1 Artefakte' in label_a


# ---------------------------------------------------------------------------
# Service — get_run_detail
# ---------------------------------------------------------------------------


def test_get_run_detail_returns_none_for_unknown(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    assert get_run_detail(settings, 'run-missing') is None


def test_get_run_detail_case_insensitive(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    detail = get_run_detail(settings, 'RUN-A')
    assert isinstance(detail, RunDetail)
    assert detail.summary.job_run_id == 'run-A'


def test_get_run_detail_loads_event_and_artifact_streams(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    detail = get_run_detail(settings, 'run-A')
    assert detail is not None
    assert isinstance(detail.summary, RunSummary)
    assert detail.summary.run_status == 'success'
    assert [e.run_event_id for e in detail.events] == ['ev-A1', 'ev-A2']
    assert detail.events[0].severity == 'info'
    assert detail.events[1].severity == 'warn'
    assert [a.run_artifact_id for a in detail.artifacts] == ['art-A1']
    assert detail.artifacts[0].ref_label == 'raw/nflverse_bulk/sf-001.csv'


def test_get_run_detail_returns_empty_streams_when_no_events_or_artifacts(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_job_definition(
            con, job_id='j-solo', job_key='solo_job', job_type='custom',
        )
        _seed_job_run(
            con,
            job_run_id='run-solo',
            job_id='j-solo',
            run_status='success',
            started_at=datetime(2024, 9, 15, 10, 0, 0),
            finished_at=datetime(2024, 9, 15, 10, 0, 1),
        )
    finally:
        con.close()
    build_run_evidence_v1(settings)

    detail = get_run_detail(settings, 'run-solo')
    assert detail is not None
    assert detail.events == ()
    assert detail.artifacts == ()
    assert detail.summary.event_count == 0
    assert detail.summary.artifact_count == 0


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_render_runs_page_empty_shows_hint(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    html = render_runs_page(settings)
    assert 'Noch keine Runs' in html
    assert 'mart-rebuild --mart-key run_evidence_v1' in html


def test_render_runs_page_with_rows(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    html = render_runs_page(settings)
    assert 'data-testid="run-row"' in html
    assert 'data-job-run-id="run-A"' in html
    assert 'data-job-run-id="run-B"' in html
    assert '/runs/run-B' in html
    assert 'Fehlgeschlagen' in html


def test_render_runs_page_with_status_filter_breadcrumb(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    html = render_runs_page(settings, status='failed')
    assert 'Runs · failed' in html
    assert 'data-job-run-id="run-B"' in html
    assert 'data-job-run-id="run-A"' not in html


def test_render_run_detail_page_404(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    build_run_evidence_v1(settings)

    html = render_run_detail_page(settings, 'run-ghost')
    assert 'Run nicht gefunden' in html
    assert 'run-ghost' in html


def test_render_run_detail_page_happy(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    html = render_run_detail_page(settings, 'run-A')
    assert 'data-testid="run-header"' in html
    assert 'data-job-run-id="run-A"' in html
    assert 'data-testid="run-event-row"' in html
    assert 'ev-A1' in html
    assert 'ev-A2' in html
    assert 'data-testid="run-artifact-row"' in html
    assert 'sf-001' in html


def test_render_run_detail_page_events_only_shows_artifact_empty_state(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    html = render_run_detail_page(settings, 'run-B')
    assert 'Keine Artefakte für diesen Run' in html
    assert 'data-testid="run-event-row"' in html


def test_render_run_detail_page_cold_start_shows_event_empty_state(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_job_definition(
            con, job_id='j-solo', job_key='solo_job', job_type='custom',
        )
        _seed_job_run(
            con,
            job_run_id='run-solo',
            job_id='j-solo',
            run_status='success',
            started_at=datetime(2024, 9, 15, 10, 0, 0),
            finished_at=datetime(2024, 9, 15, 10, 0, 1),
        )
    finally:
        con.close()
    build_run_evidence_v1(settings)

    html = render_run_detail_page(settings, 'run-solo')
    assert 'Keine Events für diesen Run' in html
    assert 'Keine Artefakte für diesen Run' in html


# ---------------------------------------------------------------------------
# Runner integration
# ---------------------------------------------------------------------------


def test_runner_executor_mart_build_accepts_run_evidence_v1(tmp_path, monkeypatch) -> None:
    from new_nfl.jobs import (
        enqueue_job,
        register_job,
        register_retry_policy,
        run_worker_once,
    )

    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()

    register_retry_policy(
        settings,
        policy_key='only_one',
        max_attempts=1,
        backoff_kind='fixed',
        base_seconds=0,
    )
    register_job(
        settings,
        job_key='mart_build_run_evidence',
        job_type='mart_build',
        retry_policy_key='only_one',
    )
    enqueue_job(
        settings,
        job_key='mart_build_run_evidence',
        params={'mart_key': 'run_evidence_v1'},
    )
    tick = run_worker_once(settings, worker_id='w')
    assert tick.run_status == 'success', tick.message
    assert tick.detail['qualified_table'] == MART_RUN_OVERVIEW_V1
    assert tick.detail['row_count'] >= 3


# ---------------------------------------------------------------------------
# Mart-table presence assertions
# ---------------------------------------------------------------------------


def test_build_run_evidence_v1_creates_all_three_marts(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_happy_runset(con)
    finally:
        con.close()
    build_run_evidence_v1(settings)

    con = duckdb.connect(str(settings.db_path))
    try:
        for table in (MART_RUN_OVERVIEW_V1, MART_RUN_EVENT_V1, MART_RUN_ARTIFACT_V1):
            assert con.execute(f"DESCRIBE {table}").fetchall()
    finally:
        con.close()
