"""Core promotion for ``core.roster_membership`` (T2.5D, ADR-0031 + ADR-0032).

First bitemporal domain in the project. Collapses the Tier-A weekly snapshot
stage (``stg.nflverse_bulk_rosters``) into ``(player_id, team_id, season,
valid_from_week, valid_to_week)`` intervals with right-open semantics
(``valid_to_week IS NULL`` while the interval is still observed in the
latest snapshot). Intervals also break on attribute changes (position,
jersey_number, status) — see ADR-0032 for the rationale.

Derived ``meta.roster_event`` rows materialize transitions between
intervals: ``trade`` (contiguous team switch), ``released`` / ``signed``
(team switch with a feed gap), and ``promoted`` / ``demoted`` (same team,
status transition between ``active`` and ``practice_squad``).

Tier-B cross-checks compare ``position`` / ``jersey_number`` / ``status``
at the ``(player_id, team_id, season, week)`` grain against the Tier-B
stage; disagreements open ``meta.quarantine_case`` with ``scope_type=
'roster_membership'`` and ``reason_code='tier_b_disagreement'``.

The result dataclass satisfies :class:`new_nfl.core.result.CoreLoadResultLike`
so CLI/runner code can print common evidence without an isinstance branch.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import duckdb

from new_nfl.adapters.slices import (
    SliceSpec,
    cross_check_slices_for_primary,
    get_slice,
    primary_slice_for_core_table,
)
from new_nfl.jobs.quarantine import open_quarantine_case
from new_nfl.mart.roster_current import build_roster_current_v1
from new_nfl.mart.roster_history import build_roster_history_v1
from new_nfl.metadata import create_ingest_run, record_load_event
from new_nfl.settings import Settings

CORE_ROSTER_TABLE = "core.roster_membership"
META_ROSTER_EVENT_TABLE = "meta.roster_event"

_REQUIRED_TIER_A_COLUMNS: tuple[str, ...] = (
    "player_id",
    "team_id",
    "season",
    "week",
)

_CROSS_CHECK_FIELDS: tuple[str, ...] = (
    "position",
    "jersey_number",
    "status",
)


@dataclass(frozen=True)
class ConflictRow:
    player_id: str
    team_id: str
    season: int
    week: int
    field: str
    tier_a_value: str | None
    tier_b_value: str | None
    tier_b_adapter_id: str

    @property
    def scope_ref(self) -> str:
        return f"{self.player_id}:{self.team_id}:{self.season}:W{self.week:02d}"


@dataclass(frozen=True)
class CoreRosterLoadResult:
    primary_slice: SliceSpec
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    distinct_player_count: int
    invalid_row_count: int
    interval_count: int
    open_interval_count: int
    event_count: int
    trade_event_count: int
    conflict_count: int
    opened_quarantine_case_ids: tuple[str, ...]
    cross_check_slice_keys: tuple[str, ...]
    load_event_id: str
    mart_qualified_table: str
    mart_row_count: int
    history_qualified_table: str
    history_row_count: int


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _describe_columns(con: duckdb.DuckDBPyConnection, qualified_table: str) -> set[str]:
    try:
        rows = con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f"{qualified_table} does not exist; run stage-load --slice rosters first"
        ) from exc
    return {str(row[0]).strip().lower() for row in rows}


def _assert_required_columns(
    con: duckdb.DuckDBPyConnection,
    qualified_table: str,
    required: Iterable[str],
) -> set[str]:
    present = _describe_columns(con, qualified_table)
    missing = sorted(set(required) - present)
    if missing:
        raise ValueError(
            f"{qualified_table} is missing required rosters columns: {', '.join(missing)}"
        )
    return present


def _opt(col: str, present: set[str]) -> str:
    return col if col in present else "NULL"


def _profile_tier_a(
    con: duckdb.DuckDBPyConnection, stage_table: str
) -> tuple[int, int, int]:
    source_row_count = int(
        con.execute(f"SELECT COUNT(*) FROM {stage_table}").fetchone()[0]
    )
    distinct_player_count = int(
        con.execute(
            f"""
            SELECT COUNT(DISTINCT UPPER(TRIM(player_id)))
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
            """
        ).fetchone()[0]
    )
    invalid_row_count = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NULL
               OR NULLIF(TRIM(team_id), '') IS NULL
               OR TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER) IS NULL
               OR TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER) IS NULL
            """
        ).fetchone()[0]
    )
    return source_row_count, distinct_player_count, invalid_row_count


# ---------------------------------------------------------------------------
# Interval rebuild
# ---------------------------------------------------------------------------


def _rebuild_core_roster(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    stage_columns: set[str],
) -> int:
    """Collapse weekly snapshots into bitemporal intervals.

    Intervals break on any change to ``(team_id, position, jersey_number,
    status)``. ``valid_to_week`` is ``NULL`` when the interval's max week
    equals the globally observed max week for the season (right-open); else
    it holds the last confirmed week.
    """
    position = _opt("position", stage_columns)
    jersey_number = _opt("jersey_number", stage_columns)
    status = _opt("status", stage_columns)
    loaded_at = "_loaded_at" if "_loaded_at" in stage_columns else "NULL"
    source_file_id = "_source_file_id" if "_source_file_id" in stage_columns else "NULL"
    adapter_id = "_adapter_id" if "_adapter_id" in stage_columns else "NULL"

    con.execute("CREATE SCHEMA IF NOT EXISTS core")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {CORE_ROSTER_TABLE} AS
        WITH normalized AS (
            SELECT
                UPPER(TRIM(player_id)) AS player_id,
                UPPER(TRIM(team_id)) AS team_id,
                TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER) AS season,
                TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER) AS week,
                UPPER(NULLIF(TRIM(CAST({position} AS VARCHAR)), '')) AS position,
                TRY_CAST(NULLIF(TRIM(CAST({jersey_number} AS VARCHAR)), '') AS INTEGER)
                    AS jersey_number,
                LOWER(NULLIF(TRIM(CAST({status} AS VARCHAR)), '')) AS status,
                COALESCE({source_file_id}, '') AS _source_file_id,
                COALESCE({adapter_id}, '') AS _adapter_id,
                {loaded_at} AS _loaded_at
            FROM {stage_table}
            WHERE NULLIF(TRIM(player_id), '') IS NOT NULL
              AND NULLIF(TRIM(team_id), '') IS NOT NULL
              AND TRY_CAST(NULLIF(TRIM(CAST(season AS VARCHAR)), '') AS INTEGER) IS NOT NULL
              AND TRY_CAST(NULLIF(TRIM(CAST(week AS VARCHAR)), '') AS INTEGER) IS NOT NULL
        ),
        deduped AS (
            SELECT player_id, team_id, season, week,
                   position, jersey_number, status,
                   _source_file_id, _adapter_id, _loaded_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY player_id, team_id, season, week
                       ORDER BY _loaded_at DESC NULLS LAST, _source_file_id DESC
                   ) AS _rn
            FROM normalized
        ),
        one_per_week AS (
            SELECT * EXCLUDE (_rn) FROM deduped WHERE _rn = 1
        ),
        season_max AS (
            SELECT season, MAX(week) AS global_max_week
            FROM one_per_week
            GROUP BY season
        ),
        grouped AS (
            SELECT o.*,
                   o.week - ROW_NUMBER() OVER (
                       PARTITION BY o.player_id, o.team_id, o.season,
                                    o.position, o.jersey_number, o.status
                       ORDER BY o.week
                   ) AS grp
            FROM one_per_week o
        ),
        intervals AS (
            SELECT
                player_id, team_id, season,
                position, jersey_number, status,
                MIN(week) AS valid_from_week,
                MAX(week) AS raw_valid_to_week,
                MIN(_loaded_at) AS _first_loaded_at,
                MAX(_loaded_at) AS _last_loaded_at,
                ANY_VALUE(_source_file_id) AS _source_file_id,
                ANY_VALUE(_adapter_id) AS _adapter_id
            FROM grouped
            GROUP BY player_id, team_id, season, position, jersey_number, status, grp
        )
        SELECT
            i.player_id,
            i.team_id,
            i.season,
            i.valid_from_week,
            CASE
                WHEN i.raw_valid_to_week >= sm.global_max_week THEN NULL
                ELSE i.raw_valid_to_week
            END AS valid_to_week,
            i.raw_valid_to_week AS last_observed_week,
            sm.global_max_week,
            i.position,
            i.jersey_number,
            i.status,
            i._first_loaded_at,
            i._last_loaded_at,
            i._source_file_id,
            i._adapter_id,
            CURRENT_TIMESTAMP AS _canonicalized_at
        FROM intervals i
        JOIN season_max sm ON sm.season = i.season
        ORDER BY player_id, season, valid_from_week, team_id
        """
    )
    return int(
        con.execute(f"SELECT COUNT(*) FROM {CORE_ROSTER_TABLE}").fetchone()[0]
    )


# ---------------------------------------------------------------------------
# Roster events
# ---------------------------------------------------------------------------


def _ensure_meta_roster_event(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS meta")
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {META_ROSTER_EVENT_TABLE} (
            roster_event_id VARCHAR PRIMARY KEY,
            event_kind VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            player_id VARCHAR NOT NULL,
            from_team_id VARCHAR,
            to_team_id VARCHAR,
            evidence_json VARCHAR NOT NULL,
            ingest_run_id VARCHAR,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _rebuild_roster_events(
    con: duckdb.DuckDBPyConnection, *, ingest_run_id: str
) -> tuple[int, int]:
    """Derive transition events from the freshly rebuilt intervals.

    Returns ``(event_count, trade_event_count)``. The table is wiped and
    rebuilt idempotently — replaying the promoter yields the same events.
    """
    _ensure_meta_roster_event(con)
    con.execute(f"DELETE FROM {META_ROSTER_EVENT_TABLE}")

    rows = con.execute(
        f"""
        SELECT player_id, team_id, season, valid_from_week, valid_to_week,
               status
        FROM {CORE_ROSTER_TABLE}
        ORDER BY player_id, season, valid_from_week, team_id
        """
    ).fetchall()

    # Group intervals by (player_id, season) preserving order.
    grouped: dict[tuple[str, int], list[tuple]] = {}
    for row in rows:
        key = (str(row[0]), int(row[2]))
        grouped.setdefault(key, []).append(row)

    event_count = 0
    trade_count = 0

    con.begin()
    try:
        for (player_id, season), intervals in grouped.items():
            prev = None
            for interval in intervals:
                _, team_id, _, valid_from, valid_to, status = interval
                team_id = str(team_id)
                status = str(status) if status is not None else None
                if prev is None:
                    if valid_from > 1:
                        _insert_event(
                            con,
                            event_kind="signed",
                            season=season,
                            week=int(valid_from),
                            player_id=player_id,
                            from_team_id=None,
                            to_team_id=team_id,
                            evidence={
                                "to_valid_from_week": int(valid_from),
                                "reason": "first_interval_after_week_1",
                            },
                            ingest_run_id=ingest_run_id,
                        )
                        event_count += 1
                    prev = interval
                    continue
                _, prev_team, _, _, prev_valid_to, prev_status = prev
                prev_team = str(prev_team)
                prev_status = str(prev_status) if prev_status is not None else None
                if prev_team == team_id:
                    # same team, attribute change (status transition or
                    # jersey/position change we don't emit an event for).
                    if (
                        prev_status != status
                        and prev_status in ("practice_squad", "active")
                        and status in ("practice_squad", "active")
                    ):
                        kind = (
                            "promoted"
                            if prev_status == "practice_squad" and status == "active"
                            else "demoted"
                            if prev_status == "active" and status == "practice_squad"
                            else "status_change"
                        )
                        _insert_event(
                            con,
                            event_kind=kind,
                            season=season,
                            week=int(valid_from),
                            player_id=player_id,
                            from_team_id=team_id,
                            to_team_id=team_id,
                            evidence={
                                "previous_status": prev_status,
                                "new_status": status,
                                "valid_from_week": int(valid_from),
                            },
                            ingest_run_id=ingest_run_id,
                        )
                        event_count += 1
                else:
                    if prev_valid_to is not None and int(valid_from) == int(prev_valid_to) + 1:
                        _insert_event(
                            con,
                            event_kind="trade",
                            season=season,
                            week=int(valid_from),
                            player_id=player_id,
                            from_team_id=prev_team,
                            to_team_id=team_id,
                            evidence={
                                "from_valid_to_week": int(prev_valid_to),
                                "to_valid_from_week": int(valid_from),
                            },
                            ingest_run_id=ingest_run_id,
                        )
                        event_count += 1
                        trade_count += 1
                    else:
                        release_week = (
                            int(prev_valid_to) + 1
                            if prev_valid_to is not None
                            else int(valid_from)
                        )
                        _insert_event(
                            con,
                            event_kind="released",
                            season=season,
                            week=release_week,
                            player_id=player_id,
                            from_team_id=prev_team,
                            to_team_id=None,
                            evidence={
                                "from_valid_to_week": (
                                    int(prev_valid_to) if prev_valid_to is not None else None
                                ),
                            },
                            ingest_run_id=ingest_run_id,
                        )
                        _insert_event(
                            con,
                            event_kind="signed",
                            season=season,
                            week=int(valid_from),
                            player_id=player_id,
                            from_team_id=None,
                            to_team_id=team_id,
                            evidence={
                                "to_valid_from_week": int(valid_from),
                                "gap_after_week": (
                                    int(prev_valid_to) if prev_valid_to is not None else None
                                ),
                            },
                            ingest_run_id=ingest_run_id,
                        )
                        event_count += 2
                prev = interval
        con.commit()
    except Exception:
        con.rollback()
        raise

    return event_count, trade_count


def _insert_event(
    con: duckdb.DuckDBPyConnection,
    *,
    event_kind: str,
    season: int,
    week: int,
    player_id: str,
    from_team_id: str | None,
    to_team_id: str | None,
    evidence: dict[str, object],
    ingest_run_id: str,
) -> None:
    import json
    import uuid

    con.execute(
        f"""
        INSERT INTO {META_ROSTER_EVENT_TABLE}
            (roster_event_id, event_kind, season, week, player_id,
             from_team_id, to_team_id, evidence_json, ingest_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid.uuid4()),
            event_kind,
            int(season),
            int(week),
            player_id,
            from_team_id,
            to_team_id,
            json.dumps(evidence, sort_keys=True, ensure_ascii=False),
            ingest_run_id or None,
        ],
    )


# ---------------------------------------------------------------------------
# Tier-B conflict detection
# ---------------------------------------------------------------------------


def _detect_conflicts(
    con: duckdb.DuckDBPyConnection,
    *,
    tier_a_stage: str,
    tier_a_columns: set[str],
    cross_check_slices: list[SliceSpec],
) -> list[ConflictRow]:
    conflicts: list[ConflictRow] = []
    for spec in cross_check_slices:
        try:
            tier_b_columns = _describe_columns(con, spec.stage_qualified_table)
        except ValueError:
            continue
        required_b = {"player_id", "team_id", "season", "week"}
        if not required_b.issubset(tier_b_columns):
            continue
        comparable = [
            field
            for field in _CROSS_CHECK_FIELDS
            if field in tier_a_columns and field in tier_b_columns
        ]
        for field in comparable:
            rows = con.execute(
                f"""
                SELECT
                    UPPER(TRIM(a.player_id)) AS player_id,
                    UPPER(TRIM(a.team_id)) AS team_id,
                    TRY_CAST(a.season AS INTEGER) AS season,
                    TRY_CAST(a.week AS INTEGER) AS week,
                    NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') AS tier_a_value,
                    NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') AS tier_b_value
                FROM {tier_a_stage} a
                JOIN {spec.stage_qualified_table} b
                  ON UPPER(TRIM(a.player_id)) = UPPER(TRIM(b.player_id))
                 AND UPPER(TRIM(a.team_id)) = UPPER(TRIM(b.team_id))
                 AND TRY_CAST(a.season AS INTEGER) = TRY_CAST(b.season AS INTEGER)
                 AND TRY_CAST(a.week AS INTEGER) = TRY_CAST(b.week AS INTEGER)
                WHERE NULLIF(TRIM(CAST(a.{field} AS VARCHAR)), '') IS NOT NULL
                  AND NULLIF(TRIM(CAST(b.{field} AS VARCHAR)), '') IS NOT NULL
                  AND LOWER(TRIM(CAST(a.{field} AS VARCHAR)))
                      <> LOWER(TRIM(CAST(b.{field} AS VARCHAR)))
                ORDER BY player_id, team_id, season, week
                """
            ).fetchall()
            for player_id, team_id, season, week, tier_a_value, tier_b_value in rows:
                if season is None or week is None:
                    continue
                conflicts.append(
                    ConflictRow(
                        player_id=str(player_id),
                        team_id=str(team_id),
                        season=int(season),
                        week=int(week),
                        field=field,
                        tier_a_value=tier_a_value,
                        tier_b_value=tier_b_value,
                        tier_b_adapter_id=spec.adapter_id,
                    )
                )
    return conflicts


def _open_conflict_quarantine(
    settings: Settings,
    *,
    ingest_run_id: str,
    primary: SliceSpec,
    conflicts: list[ConflictRow],
) -> list[str]:
    by_scope: dict[str, list[ConflictRow]] = {}
    for c in conflicts:
        by_scope.setdefault(c.scope_ref, []).append(c)
    case_ids: list[str] = []
    for scope_ref, scope_conflicts in sorted(by_scope.items()):
        evidence = [
            {
                "field": c.field,
                "tier_a_value": c.tier_a_value,
                "tier_b_value": c.tier_b_value,
                "tier_b_adapter_id": c.tier_b_adapter_id,
                "tier_a_adapter_id": primary.adapter_id,
                "player_id": c.player_id,
                "team_id": c.team_id,
                "season": c.season,
                "week": c.week,
                "ingest_run_id": ingest_run_id,
            }
            for c in scope_conflicts
        ]
        case = open_quarantine_case(
            settings,
            scope_type="roster_membership",
            scope_ref=scope_ref,
            reason_code="tier_b_disagreement",
            severity="warning",
            evidence_refs=evidence,
            notes=(
                f"Tier-A ({primary.adapter_id}) vs Tier-B disagreement on "
                f"{len(scope_conflicts)} field(s) at {scope_ref}; "
                "Tier-A wins in core.roster_membership."
            ),
        )
        case_ids.append(case.quarantine_case_id)
    return case_ids


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def execute_core_roster_load(
    settings: Settings,
    *,
    execute: bool,
) -> CoreRosterLoadResult:
    primary = primary_slice_for_core_table(CORE_ROSTER_TABLE)
    if primary is None:
        primary = get_slice("nflverse_bulk", "rosters")
    cross_checks = cross_check_slices_for_primary(primary)
    pipeline_name = f"adapter.{primary.adapter_id}.core_load.rosters"

    con = duckdb.connect(str(settings.db_path))
    try:
        tier_a_columns = _assert_required_columns(
            con, primary.stage_qualified_table, _REQUIRED_TIER_A_COLUMNS
        )
        source_row_count, distinct_player_count, invalid_row_count = _profile_tier_a(
            con, primary.stage_qualified_table
        )
        if not execute:
            return CoreRosterLoadResult(
                primary_slice=primary,
                run_mode="dry_run",
                run_status="planned_core_roster_load",
                pipeline_name=pipeline_name,
                ingest_run_id="",
                qualified_table=CORE_ROSTER_TABLE,
                source_row_count=source_row_count,
                row_count=0,
                distinct_player_count=distinct_player_count,
                invalid_row_count=invalid_row_count,
                interval_count=0,
                open_interval_count=0,
                event_count=0,
                trade_event_count=0,
                conflict_count=0,
                opened_quarantine_case_ids=(),
                cross_check_slice_keys=tuple(
                    spec.adapter_id for spec in cross_checks
                ),
                load_event_id="",
                mart_qualified_table="",
                mart_row_count=0,
                history_qualified_table="",
                history_row_count=0,
            )
        row_count = _rebuild_core_roster(
            con, primary.stage_qualified_table, tier_a_columns
        )
        open_interval_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {CORE_ROSTER_TABLE} WHERE valid_to_week IS NULL"
            ).fetchone()[0]
        )
        conflicts = _detect_conflicts(
            con,
            tier_a_stage=primary.stage_qualified_table,
            tier_a_columns=tier_a_columns,
            cross_check_slices=cross_checks,
        )
    finally:
        con.close()

    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        adapter_id=primary.adapter_id,
        run_mode="execute",
        run_status="core_roster_loaded",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=1,
        message="T2.5D core.roster_membership promotion (bitemporal, ADR-0032)",
    )

    con = duckdb.connect(str(settings.db_path))
    try:
        event_count, trade_event_count = _rebuild_roster_events(
            con, ingest_run_id=ingest_run_id
        )
    finally:
        con.close()

    opened_case_ids = _open_conflict_quarantine(
        settings,
        ingest_run_id=ingest_run_id,
        primary=primary,
        conflicts=conflicts,
    )
    current_result = build_roster_current_v1(settings)
    history_result = build_roster_history_v1(settings)
    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        source_id=primary.adapter_id,
        pipeline_name=pipeline_name,
        event_kind="core_loaded",
        target_schema="core",
        target_object="roster_membership",
        row_count=row_count,
        object_path=primary.stage_qualified_table,
        payload={
            "source_table": primary.stage_qualified_table,
            "qualified_table": CORE_ROSTER_TABLE,
            "source_row_count": source_row_count,
            "distinct_player_count": distinct_player_count,
            "invalid_row_count": invalid_row_count,
            "interval_count": row_count,
            "open_interval_count": open_interval_count,
            "event_count": event_count,
            "trade_event_count": trade_event_count,
            "conflict_count": len(conflicts),
            "opened_quarantine_case_ids": opened_case_ids,
            "mart_qualified_table": current_result.qualified_table,
            "mart_row_count": current_result.row_count,
            "history_qualified_table": history_result.qualified_table,
            "history_row_count": history_result.row_count,
        },
    )
    return CoreRosterLoadResult(
        primary_slice=primary,
        run_mode="execute",
        run_status="core_roster_loaded",
        pipeline_name=pipeline_name,
        ingest_run_id=ingest_run_id,
        qualified_table=CORE_ROSTER_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        distinct_player_count=distinct_player_count,
        invalid_row_count=invalid_row_count,
        interval_count=row_count,
        open_interval_count=open_interval_count,
        event_count=event_count,
        trade_event_count=trade_event_count,
        conflict_count=len(conflicts),
        opened_quarantine_case_ids=tuple(opened_case_ids),
        cross_check_slice_keys=tuple(spec.adapter_id for spec in cross_checks),
        load_event_id=load_event_id,
        mart_qualified_table=current_result.qualified_table,
        mart_row_count=current_result.row_count,
        history_qualified_table=history_result.qualified_table,
        history_row_count=history_result.row_count,
    )


__all__ = [
    "CORE_ROSTER_TABLE",
    "META_ROSTER_EVENT_TABLE",
    "ConflictRow",
    "CoreRosterLoadResult",
    "execute_core_roster_load",
]
