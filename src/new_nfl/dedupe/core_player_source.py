"""Bridge between ``core.player`` and the dedupe pipeline (T2.5C, ADR-0027).

The dedupe pipeline from T2.4B ships with ``DEMO_PLAYER_RECORDS`` as its only
input source; T2.5C delivers the first real application by reading rows from
``core.player`` directly. Each ``core.player`` row becomes a
``RawPlayerRecord`` keyed by its canonical ``player_id``; downstream stages
(normalize → block → score → cluster → review) remain untouched.

``birth_year`` is derived from ``birth_date`` when present — the current
``RuleBasedPlayerScorer`` uses it as a strong disambiguation signal for
same-name, different-person pairs (Patrick Mahomes Sr. vs. Jr. is the
canonical test case).
"""
from __future__ import annotations

import duckdb

from new_nfl.core.players import CORE_PLAYER_TABLE
from new_nfl.dedupe.normalize import RawPlayerRecord
from new_nfl.dedupe.pipeline import DedupeRunResult, run_player_dedupe
from new_nfl.settings import Settings

_DEFAULT_SOURCE_REF = "core.player"


def read_core_player_records(
    settings: Settings,
    *,
    source_ref: str = _DEFAULT_SOURCE_REF,
) -> list[RawPlayerRecord]:
    """Read ``core.player`` and project each row into a ``RawPlayerRecord``.

    Raises ``ValueError`` if ``core.player`` does not exist yet — callers
    should run ``execute_core_player_load --execute`` first.
    """
    con = duckdb.connect(str(settings.db_path))
    try:
        try:
            rows = con.execute(
                f"""
                SELECT
                    player_id,
                    display_name,
                    position,
                    EXTRACT(YEAR FROM birth_date) AS birth_year
                FROM {CORE_PLAYER_TABLE}
                WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
                  AND NULLIF(TRIM(display_name), '') IS NOT NULL
                ORDER BY player_id
                """
            ).fetchall()
        except duckdb.Error as exc:
            raise ValueError(
                f"{CORE_PLAYER_TABLE} does not exist; run "
                "core-load --slice players --execute first"
            ) from exc
    finally:
        con.close()
    records: list[RawPlayerRecord] = []
    for player_id, display_name, position, birth_year in rows:
        records.append(
            RawPlayerRecord(
                record_id=str(player_id),
                full_name=str(display_name),
                position=str(position) if position is not None else None,
                birth_year=int(birth_year) if birth_year is not None else None,
                source_ref=source_ref,
            )
        )
    return records


def run_player_dedupe_from_core(
    settings: Settings,
    *,
    source_ref: str = _DEFAULT_SOURCE_REF,
    lower_threshold: float = 0.50,
    upper_threshold: float = 0.85,
) -> DedupeRunResult:
    """Run the dedupe pipeline against the current ``core.player`` snapshot."""
    records = read_core_player_records(settings, source_ref=source_ref)
    return run_player_dedupe(
        settings,
        records=records,
        source_ref=source_ref,
        lower_threshold=lower_threshold,
        upper_threshold=upper_threshold,
    )


__all__ = [
    "read_core_player_records",
    "run_player_dedupe_from_core",
]
