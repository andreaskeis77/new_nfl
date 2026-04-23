"""T2.7B — :mod:`new_nfl.observability.logging` + runner hooks.

Covers:

* record envelope shape (``event_id``, ``ts``, ``level``, ``msg``, ``details``)
  plus optional ``adapter_id`` / ``source_file_id`` / ``job_run_id``
* ``NEW_NFL_LOG_LEVEL`` / ``NEW_NFL_LOG_DESTINATION`` env wiring via
  :class:`new_nfl.settings.Settings`
* severity filtering — below-threshold events return ``None`` and emit
  no I/O
* stdout destination produces one JSON line per event
* ``file:`` destination writes ``events_YYYYMMDD.jsonl`` under the path
  and creates the directory on first use
* unsupported levels + unsupported destinations raise ``ValueError``
* runner hook — ``_executor_custom`` emits ``executor_start`` +
  ``executor_complete`` events tagged with the dispatched job_type
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from new_nfl.jobs.runner import _executor_custom
from new_nfl.observability.logging import (
    SUPPORTED_LEVELS,
    StructuredLogger,
    get_logger,
)
from new_nfl.settings import load_settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_lines(raw: str) -> list[dict]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Record shape + filtering
# ---------------------------------------------------------------------------


def test_event_record_carries_all_mandatory_fields(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "stdout")
    logger = get_logger(load_settings())
    record = logger.event("INFO", "hello", details={"k": 1})
    assert record is not None
    assert set(record.keys()) >= {"event_id", "ts", "level", "msg", "details"}
    assert record["level"] == "INFO"
    assert record["msg"] == "hello"
    assert record["details"] == {"k": 1}
    assert record["ts"].endswith("Z")


def test_optional_context_fields_attach_only_when_supplied(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "stdout")
    logger = get_logger(load_settings())
    bare = logger.event("INFO", "bare")
    assert bare is not None
    assert "adapter_id" not in bare
    enriched = logger.event(
        "WARN",
        "enriched",
        adapter_id="nflv",
        source_file_id="src-1",
        job_run_id="jr-1",
    )
    assert enriched is not None
    assert enriched["adapter_id"] == "nflv"
    assert enriched["source_file_id"] == "src-1"
    assert enriched["job_run_id"] == "jr-1"


def test_level_below_threshold_is_filtered(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "WARN")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "stdout")
    logger = get_logger(load_settings())
    buf = io.StringIO()
    with redirect_stdout(buf):
        dropped = logger.event("INFO", "below")
        emitted = logger.event("ERROR", "above")
    assert dropped is None
    assert emitted is not None
    lines = _parse_lines(buf.getvalue())
    assert len(lines) == 1
    assert lines[0]["msg"] == "above"


def test_unknown_level_raises(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "stdout")
    logger = get_logger(load_settings())
    with pytest.raises(ValueError, match="unsupported log level"):
        logger.event("TRACE", "nope")  # type: ignore[arg-type]


def test_supported_levels_cover_standard_hierarchy() -> None:
    assert SUPPORTED_LEVELS == ("DEBUG", "INFO", "WARN", "ERROR")


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------


def test_stdout_destination_emits_valid_json_lines(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "stdout")
    logger = get_logger(load_settings())
    buf = io.StringIO()
    with redirect_stdout(buf):
        logger.event("INFO", "one", details={"n": 1})
        logger.event("INFO", "two", details={"n": 2})
    lines = _parse_lines(buf.getvalue())
    assert [line["msg"] for line in lines] == ["one", "two"]
    assert [line["details"]["n"] for line in lines] == [1, 2]


def test_file_destination_appends_per_day_file(tmp_path, monkeypatch) -> None:
    target = tmp_path / "logs"
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", f"file:{target}")
    logger = get_logger(load_settings())
    logger.event("INFO", "a")
    logger.event("INFO", "b")
    assert target.is_dir()
    files = list(target.glob("events_*.jsonl"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    lines = _parse_lines(content)
    assert [line["msg"] for line in lines] == ["a", "b"]


def test_file_destination_creates_parent_dir_lazily(tmp_path, monkeypatch) -> None:
    target = tmp_path / "deep" / "nested" / "logs"
    assert not target.exists()
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", f"file:{target}")
    get_logger(load_settings()).event("INFO", "hello")
    assert target.is_dir()


def test_unsupported_destination_raises(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "kafka://topic")
    with pytest.raises(ValueError, match="unsupported log destination"):
        get_logger(load_settings())


def test_empty_file_destination_raises(monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", "file:")
    with pytest.raises(ValueError, match="non-empty path"):
        get_logger(load_settings())


def test_settings_defaults_produce_stdout_info_logger(monkeypatch) -> None:
    monkeypatch.delenv("NEW_NFL_LOG_LEVEL", raising=False)
    monkeypatch.delenv("NEW_NFL_LOG_DESTINATION", raising=False)
    logger = get_logger(load_settings())
    assert isinstance(logger, StructuredLogger)
    assert logger.destination == "stdout"
    # default level is INFO → severity 20
    assert logger.min_severity == 20


# ---------------------------------------------------------------------------
# Runner hook — _executor_custom
# ---------------------------------------------------------------------------


def test_executor_custom_emits_start_and_complete_events(
    tmp_path, monkeypatch,
) -> None:
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NEW_NFL_LOG_DESTINATION", f"file:{log_dir}")
    settings = load_settings()
    result = _executor_custom(settings, {"note": "unit-test"})
    assert result.success is True
    files = list(log_dir.glob("events_*.jsonl"))
    assert len(files) == 1
    records = _parse_lines(files[0].read_text(encoding="utf-8"))
    msgs = [record["msg"] for record in records]
    assert msgs.count("executor_start") == 1
    assert msgs.count("executor_complete") == 1
    start = next(r for r in records if r["msg"] == "executor_start")
    assert start["details"]["job_type"] == "custom"
    assert "digest" in start["details"]
