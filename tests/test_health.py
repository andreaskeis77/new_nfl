"""T2.7A — ``new-nfl health-probe`` / :mod:`new_nfl.observability.health`.

Covers:

* every probe envelope carries ``schema_version``, ``checked_at``,
  ``status`` and ``details`` in the right shape
* cold start (bootstrap only, no marts) → ``live=ok``, ``ready=fail``,
  ``freshness=warn`` (synthetic-stale fallback), ``deps=fail``
  (``meta.load_events`` absent)
* happy path (seeded load events + built freshness mart) → every
  probe flips to ``ok``
* warn path (open quarantine on a seeded domain) → ``freshness=warn``
* CLI plugin wiring: ``new-nfl health-probe`` round-trips through
  ``build_parser`` and dispatch prints JSON + exits with the expected
  code
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from datetime import datetime

import duckdb
import pytest

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.cli_plugins import get_cli_plugin
from new_nfl.mart import build_freshness_overview_v1
from new_nfl.observability.health import (
    SCHEMA_VERSION,
    SUPPORTED_KINDS,
    build_health_response,
    exit_code_for,
)
from new_nfl.settings import load_settings

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
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
    event_status: str = "loaded",
    event_kind: str = "core_loaded",
    row_count: int | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO meta.load_events
            (load_event_id, ingest_run_id, target_schema, target_object,
             event_kind, event_status, row_count, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"le-{target_object}-{ingest_run_id}",
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
    severity: str = "warn",
    status: str = "open",
) -> None:
    ts = datetime.now()
    con.execute(
        """
        INSERT INTO meta.quarantine_case
            (quarantine_case_id, scope_type, scope_ref, reason_code,
             severity, status, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"q-{scope_type}-{scope_ref}",
            scope_type,
            scope_ref,
            "tier_b_disagreement",
            severity,
            status,
            ts,
            ts,
        ],
    )


def _assert_envelope_shape(payload: dict) -> None:
    assert payload["schema_version"] == SCHEMA_VERSION
    checked_at = payload["checked_at"]
    assert isinstance(checked_at, str)
    assert checked_at.endswith("Z")
    # Parsable as ISO-8601 UTC
    datetime.strptime(checked_at, "%Y-%m-%dT%H:%M:%SZ")
    assert payload["status"] in ("ok", "warn", "fail")
    assert isinstance(payload["details"], dict)


# ---------------------------------------------------------------------------
# Envelope shape — one assertion per kind
# ---------------------------------------------------------------------------


def test_every_kind_returns_valid_envelope(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    for kind in SUPPORTED_KINDS:
        response = build_health_response(settings, kind)
        _assert_envelope_shape(response.to_dict())


def test_unknown_kind_raises() -> None:
    settings = load_settings()
    with pytest.raises(ValueError, match="unknown health-probe kind"):
        build_health_response(settings, "nonsense")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cold-start semantics
# ---------------------------------------------------------------------------


def test_live_is_ok_even_without_a_db(tmp_path, monkeypatch) -> None:
    # Point at a nonexistent DB path; live must not need it.
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    response = build_health_response(settings, "live")
    assert response.status == "ok"
    assert isinstance(response.details["pid"], int)


def test_ready_fails_on_cold_start_without_mart(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    response = build_health_response(settings, "ready")
    assert response.status == "fail"
    assert response.details["db_connect"] == "ok"
    assert response.details["mart_present"] is False
    assert response.details["mart_table"] == "mart.freshness_overview_v1"


def test_ready_fails_when_db_path_cannot_be_opened(tmp_path, monkeypatch) -> None:
    # Force an unreachable DB path.
    bogus = tmp_path / "not_a_dir" / "nested" / "missing.duckdb"
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_DB_PATH", str(bogus))
    settings = load_settings()
    response = build_health_response(settings, "ready")
    assert response.status == "fail"
    assert response.details["db_connect"] == "fail"


def test_freshness_reports_warn_with_synthetic_stale_rows(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    response = build_health_response(settings, "freshness")
    # synthetic-stale fallback renders six rows, all stale → warn aggregate
    assert response.status == "warn"
    assert response.details["row_count"] == 6
    assert response.details["domains_stale"] == 6
    assert response.details["domains_ok"] == 0
    rows = response.details["rows"]
    assert all(r["freshness_status"] == "stale" for r in rows)


def test_deps_fails_when_load_events_table_missing(
    tmp_path, monkeypatch,
) -> None:
    # Fresh DB file with *no* bootstrap → meta.load_events does not exist.
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    # Touch the DB so duckdb.connect succeeds (empty file is valid).
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    duckdb.connect(str(settings.db_path)).close()
    response = build_health_response(settings, "deps")
    assert response.status == "fail"
    assert response.details["load_events_present"] is False
    assert response.details["slice_count"] >= 6


# ---------------------------------------------------------------------------
# Warn / happy path with seeded events
# ---------------------------------------------------------------------------


def test_deps_warns_when_some_slices_have_no_events(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema="core",
            target_object="team",
            ingest_run_id="run-t",
            recorded_at=datetime(2026, 4, 23, 10, 0),
            row_count=32,
        )
    finally:
        con.close()
    response = build_health_response(settings, "deps")
    assert response.status == "warn"
    slices = response.details["slices"]
    by_table = {s["core_table"]: s for s in slices}
    assert by_table["core.team"]["event_count"] == 1
    assert by_table["core.team"]["last_event_at"] is not None
    # Other primary slices still have zero events.
    assert any(s["event_count"] == 0 for s in slices)


def test_deps_reports_ok_when_every_primary_slice_has_events(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        # Every distinct primary (adapter, core_table) gets a seed event.
        from new_nfl.adapters.slices import SLICE_REGISTRY

        seen: set[str] = set()
        for spec in SLICE_REGISTRY.values():
            if spec.tier_role != "primary" or not spec.core_table:
                continue
            if spec.core_table in seen:
                continue
            seen.add(spec.core_table)
            _, _, target_object = spec.core_table.partition(".")
            _seed_load_event(
                con,
                target_schema="core",
                target_object=target_object,
                ingest_run_id=f"run-{target_object}",
                recorded_at=datetime(2026, 4, 23, 12, 0),
                row_count=10,
            )
    finally:
        con.close()
    response = build_health_response(settings, "deps")
    assert response.status == "ok"
    assert response.details["slices_without_events"] == 0


def test_freshness_promotes_warn_on_open_quarantine(
    tmp_path, monkeypatch,
) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    con = duckdb.connect(str(settings.db_path))
    try:
        _seed_load_event(
            con,
            target_schema="core",
            target_object="player",
            ingest_run_id="run-pl",
            recorded_at=datetime(2026, 4, 23, 9, 0),
            row_count=3072,
        )
        _seed_quarantine(
            con,
            scope_type="player",
            scope_ref="00-0033873",
            severity="warn",
            status="open",
        )
    finally:
        con.close()
    build_freshness_overview_v1(settings)
    response = build_health_response(settings, "freshness")
    assert response.status == "warn"
    player_row = next(
        r for r in response.details["rows"] if r["domain_object"] == "player"
    )
    assert player_row["freshness_status"] == "warn"
    assert player_row["open_quarantine_count"] == 1


def test_ready_is_ok_after_freshness_mart_built(tmp_path, monkeypatch) -> None:
    settings = _bootstrap(tmp_path, monkeypatch)
    build_freshness_overview_v1(settings)
    response = build_health_response(settings, "ready")
    assert response.status == "ok"
    assert response.details["mart_present"] is True


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------


def test_exit_code_mapping() -> None:
    assert exit_code_for("ok") == 0
    assert exit_code_for("warn") == 1
    assert exit_code_for("fail") == 2


# ---------------------------------------------------------------------------
# CLI plugin wiring (ADR-0033 surface)
# ---------------------------------------------------------------------------


def test_cli_plugin_is_registered() -> None:
    import new_nfl.plugins  # noqa: F401

    plugin = get_cli_plugin("health-probe")
    assert plugin is not None
    assert plugin.name == "health-probe"


def test_cli_plugin_parser_round_trips_through_build_parser() -> None:
    from new_nfl.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["health-probe", "--kind", "live"])
    assert args.command == "health-probe"
    assert args.kind == "live"


def test_cli_plugin_dispatch_prints_json_and_returns_zero_for_live(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    plugin = get_cli_plugin("health-probe")
    assert plugin is not None
    args = argparse.Namespace(command="health-probe", kind="live", pretty=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = plugin.dispatch(args)
    payload = json.loads(buf.getvalue())
    _assert_envelope_shape(payload)
    assert payload["status"] == "ok"
    assert rc == 0


def test_cli_plugin_dispatch_returns_nonzero_when_ready_fails(
    tmp_path, monkeypatch,
) -> None:
    _bootstrap(tmp_path, monkeypatch)
    plugin = get_cli_plugin("health-probe")
    assert plugin is not None
    args = argparse.Namespace(command="health-probe", kind="ready", pretty=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = plugin.dispatch(args)
    payload = json.loads(buf.getvalue())
    assert payload["status"] == "fail"
    assert rc == 2
