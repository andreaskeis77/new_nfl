"""Replay drill for canonical core-load domains (T2.7D).

The drill snapshots the current ``core.<domain>`` into a throw-away
DuckDB file, re-runs the corresponding ``execute_core_*_load`` against
the live database, then diffs pre-state vs. post-state via
:func:`new_nfl.resilience.diff.diff_tables`. Because the core-load
pattern uses ``CREATE OR REPLACE TABLE`` on every call, a clean
idempotent re-run should produce an empty diff (excluding the
``_canonicalized_at`` / ``_loaded_at`` timestamps which are stamped per
run).

A non-empty diff on unchanged raw input is a determinism bug in the
core-load, not in the replay drill — the caller must escalate rather
than paper over it.
"""
from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from new_nfl._db import connect
from new_nfl.resilience.diff import DEFAULT_EXCLUDE_COLS, TableDiff, diff_tables
from new_nfl.settings import Settings

# ---------------------------------------------------------------------------
# Domain registry — key_cols come from the ``PARTITION BY`` in each
# ``core.<domain>`` builder. Kept here (not derived at runtime) so a future
# core-load grain change surfaces in this file as a diff instead of silently
# breaking the replay drill.
# ---------------------------------------------------------------------------

DomainLoader = Callable[[Settings], Any]


@dataclass(frozen=True)
class DomainSpec:
    domain: str
    core_table: str
    key_cols: tuple[str, ...]
    loader_import_path: str


DOMAIN_SPECS: dict[str, DomainSpec] = {
    "team": DomainSpec(
        domain="team",
        core_table="core.team",
        key_cols=("team_id",),
        loader_import_path="new_nfl.core.teams.execute_core_team_load",
    ),
    "game": DomainSpec(
        domain="game",
        core_table="core.game",
        key_cols=("game_id",),
        loader_import_path="new_nfl.core.games.execute_core_game_load",
    ),
    "player": DomainSpec(
        domain="player",
        core_table="core.player",
        key_cols=("player_id",),
        loader_import_path="new_nfl.core.players.execute_core_player_load",
    ),
    "roster_membership": DomainSpec(
        domain="roster_membership",
        core_table="core.roster_membership",
        key_cols=("player_id", "team_id", "season", "week"),
        loader_import_path="new_nfl.core.rosters.execute_core_roster_load",
    ),
    "team_stats_weekly": DomainSpec(
        domain="team_stats_weekly",
        core_table="core.team_stats_weekly",
        key_cols=("season", "week", "team_id"),
        loader_import_path=(
            "new_nfl.core.team_stats.execute_core_team_stats_load"
        ),
    ),
    "player_stats_weekly": DomainSpec(
        domain="player_stats_weekly",
        core_table="core.player_stats_weekly",
        key_cols=("season", "week", "player_id"),
        loader_import_path=(
            "new_nfl.core.player_stats.execute_core_player_stats_load"
        ),
    ),
}


@dataclass(frozen=True)
class ReplayResult:
    domain: str
    core_table: str
    source_file_id: str | None
    dry_run: bool
    pre_row_count: int
    post_row_count: int
    diff: TableDiff | None
    loader_result: Any | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_deterministic(self) -> bool:
        """``True`` iff the post-state matches the pre-state on non-excluded columns."""
        if self.dry_run or self.diff is None:
            return False
        return self.diff.is_empty


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_loader(spec: DomainSpec) -> DomainLoader:
    module_path, _, func_name = spec.loader_import_path.rpartition(".")
    import importlib

    module = importlib.import_module(module_path)
    loader = getattr(module, func_name)
    return loader


def _table_exists(con: duckdb.DuckDBPyConnection, qualified: str) -> bool:
    schema, _, table = qualified.partition(".")
    rows = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, table],
    ).fetchone()
    return bool(rows and int(rows[0]))


def _row_count(con: duckdb.DuckDBPyConnection, qualified: str) -> int:
    if not _table_exists(con, qualified):
        return 0
    return int(con.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0])


def _copy_table_to_snapshot(
    live_db_path: Path,
    snap_con: duckdb.DuckDBPyConnection,
    qualified: str,
) -> int:
    """Materialise ``qualified`` from the live DB into ``snap_con`` via ATTACH.

    Uses ``ATTACH ... (READ_ONLY) + CREATE TABLE AS SELECT`` so the copy
    is pure SQL — no Python round-trip. This is essential for columns
    typed ``TIMESTAMP WITH TIME ZONE``, which DuckDB can only materialise
    into Python datetimes via the optional ``pytz`` dependency that is
    not part of this project's base install.
    """
    schema, _, _ = qualified.partition(".")
    attach_path = live_db_path.as_posix()
    snap_con.execute(f"ATTACH '{attach_path}' AS live_src (READ_ONLY)")
    try:
        snap_con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        snap_con.execute(
            f"CREATE OR REPLACE TABLE {qualified} AS "
            f"SELECT * FROM live_src.{qualified}"
        )
        count = int(
            snap_con.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0]
        )
    finally:
        snap_con.execute("DETACH live_src")
    return count


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def replay_domain(
    settings: Settings,
    *,
    domain: str,
    source_file_id: str | None = None,
    dry_run: bool = False,
    exclude_cols: tuple[str, ...] = DEFAULT_EXCLUDE_COLS,
) -> ReplayResult:
    """Run the replay drill for ``domain`` and return the diff.

    ``source_file_id`` is informational — the core-load pattern rebuilds
    the full table from the Tier-A stage slice, so the replay is always
    a full re-run. The id is carried through the report so an operator
    can trace which run triggered the drill.

    When ``dry_run`` is ``True`` the live DB is never mutated: only the
    pre-state row count is read and reported. ``diff`` will be ``None``.
    """
    if domain not in DOMAIN_SPECS:
        known = sorted(DOMAIN_SPECS)
        raise ValueError(
            f"unknown domain={domain!r}; known domains: {known}"
        )
    spec = DOMAIN_SPECS[domain]

    if dry_run:
        live_con = connect(settings)
        try:
            pre = _row_count(live_con, spec.core_table)
        finally:
            live_con.close()
        return ReplayResult(
            domain=spec.domain,
            core_table=spec.core_table,
            source_file_id=source_file_id,
            dry_run=True,
            pre_row_count=pre,
            post_row_count=pre,
            diff=None,
            loader_result=None,
            notes=(
                f"dry_run — would re-run {spec.loader_import_path}; "
                f"pre_row_count={pre}",
            ),
        )

    loader = _resolve_loader(spec)

    with tempfile.TemporaryDirectory(prefix="new-nfl-replay-") as tmp_str:
        snapshot_path = Path(tmp_str) / "pre_state.duckdb"

        # Step 1 — snapshot live.core.<domain> into the throw-away DB.
        # The live connection is closed *before* the ATTACH so the
        # snapshot connection gets a clean read-only handle on disk.
        live_con = connect(settings)
        try:
            if not _table_exists(live_con, spec.core_table):
                raise ValueError(
                    f"{spec.core_table} does not exist; run core-load "
                    f"for {domain} first"
                )
        finally:
            live_con.close()

        snap_con = duckdb.connect(str(snapshot_path))
        try:
            pre_row_count = _copy_table_to_snapshot(
                settings.db_path, snap_con, spec.core_table
            )
        finally:
            snap_con.close()

        # Step 2 — re-run the core loader against the live DB. The loader
        # issues its own connections internally; running it outside our
        # snapshot connection avoids any double-open.
        loader_result = loader(settings, execute=True)

        # Step 3 — diff the pre-state snapshot against the live rebuild.
        live_con = connect(settings)
        snap_con = duckdb.connect(str(snapshot_path))
        try:
            post_row_count = _row_count(live_con, spec.core_table)
            diff = diff_tables(
                con_a=snap_con,
                con_b=live_con,
                table=spec.core_table,
                key_cols=spec.key_cols,
                exclude_cols=exclude_cols,
            )
        finally:
            snap_con.close()
            live_con.close()

    return ReplayResult(
        domain=spec.domain,
        core_table=spec.core_table,
        source_file_id=source_file_id,
        dry_run=False,
        pre_row_count=pre_row_count,
        post_row_count=post_row_count,
        diff=diff,
        loader_result=loader_result,
        notes=(),
    )


__all__ = [
    "DOMAIN_SPECS",
    "DomainSpec",
    "ReplayResult",
    "replay_domain",
]
