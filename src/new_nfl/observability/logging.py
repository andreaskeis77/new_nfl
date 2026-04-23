"""Structured JSON-line logger for runtime events (T2.7B).

Every event carries the mandatory envelope

.. code-block:: json

    {
        "event_id": "<uuid4>",
        "ts": "<ISO-8601 UTC with ms>",
        "level": "DEBUG" | "INFO" | "WARN" | "ERROR",
        "msg": "<short human-readable summary>",
        "details": { ... free-form payload ... }
    }

and may attach the optional runtime-context fields ``adapter_id``,
``source_file_id``, ``job_run_id`` when the caller knows them — those
are the three axes by which the downstream evidence-mart
(``mart.run_evidence_v1``) joins log events back to job/ingest runs.

Configuration comes exclusively from :class:`new_nfl.settings.Settings`:

* :attr:`Settings.log_level` (env: ``NEW_NFL_LOG_LEVEL``, default
  ``INFO``) — minimum severity emitted. Events below the threshold are
  dropped at the logger before any I/O happens.
* :attr:`Settings.log_destination` (env: ``NEW_NFL_LOG_DESTINATION``,
  default ``stdout``) — ``stdout`` streams JSON lines to
  :data:`sys.stdout`; ``file:<path>`` appends to
  ``<path>/events_YYYYMMDD.jsonl`` with one file per UTC day (the
  directory is created on first use).

The logger is intentionally dependency-free at runtime — no logging
handlers, no filters, no formatters — so it stays side-effect-free
during import and easy to drop into tight loops like the job runner's
``_executor_*`` hooks.
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from new_nfl.settings import Settings

Level = Literal["DEBUG", "INFO", "WARN", "ERROR"]
SUPPORTED_LEVELS: tuple[Level, ...] = ("DEBUG", "INFO", "WARN", "ERROR")

_LEVEL_SEVERITY: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "ERROR": 40,
}

_FILE_PREFIX = "file:"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_ts(dt: datetime) -> str:
    # Millisecond precision is enough for operator forensics and keeps
    # the JSON line short; trailing ``Z`` asserts UTC for parsers that
    # only accept explicit offsets.
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _file_for_date(base_dir: Path, dt: datetime) -> Path:
    return base_dir / f"events_{dt.strftime('%Y%m%d')}.jsonl"


def _resolve_min_severity(level_name: str) -> int:
    normalized = level_name.strip().upper() or "INFO"
    return _LEVEL_SEVERITY.get(normalized, _LEVEL_SEVERITY["INFO"])


@dataclass
class StructuredLogger:
    """Writes one JSON line per event, filtered by minimum severity.

    Callers should obtain an instance via :func:`get_logger` rather than
    constructing one directly, so that settings-driven configuration
    (level + destination) stays centralized.
    """

    min_severity: int
    destination: str
    _file_base: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.destination == "stdout":
            return
        if self.destination.startswith(_FILE_PREFIX):
            raw = self.destination[len(_FILE_PREFIX):].strip()
            if not raw:
                raise ValueError(
                    "log destination 'file:' requires a non-empty path"
                )
            base = Path(raw)
            base.mkdir(parents=True, exist_ok=True)
            self._file_base = base
            return
        raise ValueError(
            f"unsupported log destination: {self.destination!r}; "
            "expected 'stdout' or 'file:<path>'"
        )

    def _write(self, payload: str) -> None:
        # ``sys.stdout`` is re-resolved each call so ``redirect_stdout`` (and
        # pytest's capture) take effect — caching it at init would freeze
        # the reference to the real stdout and defeat redirection.
        if self._file_base is None:
            sys.stdout.write(payload + "\n")
            sys.stdout.flush()
            return
        target = _file_for_date(self._file_base, _utc_now())
        with target.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    def event(
        self,
        level: Level,
        msg: str,
        *,
        details: dict[str, Any] | None = None,
        adapter_id: str | None = None,
        source_file_id: str | None = None,
        job_run_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Emit one event; return the record emitted, or ``None`` when filtered.

        Returning the record (rather than just writing it) lets tests
        assert on the emitted shape without having to parse the JSON
        stream — and lets the runner's executor hooks thread the same
        ``event_id`` through to downstream records if we ever want
        cross-referencing.
        """
        severity = _LEVEL_SEVERITY.get(level)
        if severity is None:
            raise ValueError(
                f"unsupported log level: {level!r}; "
                f"supported: {list(SUPPORTED_LEVELS)}"
            )
        if severity < self.min_severity:
            return None
        record: dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "ts": _format_ts(_utc_now()),
            "level": level,
            "msg": msg,
            "details": dict(details) if details else {},
        }
        if adapter_id is not None:
            record["adapter_id"] = adapter_id
        if source_file_id is not None:
            record["source_file_id"] = source_file_id
        if job_run_id is not None:
            record["job_run_id"] = job_run_id
        self._write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        return record


def get_logger(settings: Settings) -> StructuredLogger:
    """Construct a :class:`StructuredLogger` wired to ``settings``."""
    return StructuredLogger(
        min_severity=_resolve_min_severity(settings.log_level),
        destination=settings.log_destination,
    )


__all__ = [
    "Level",
    "SUPPORTED_LEVELS",
    "StructuredLogger",
    "get_logger",
]
