"""Column-alias registry for slice-level schema-drift handling (T3.1S).

When upstream feeds rename columns without changing semantics, the canonical
core schema would otherwise reject the stage table at the
``_assert_required_columns`` gate. T3.1S formalises a per-slice alias map and
a single helper that renames the upstream column to the canonical name on the
stage table in place. The rename is idempotent and runs before the gate.

Background: nflverse moved several primary-slice schemas at the same time as
the URL drift fixed by ADR-0034 follow-up:

- ``players``: ``player_id`` was renamed to ``gsis_id``.
- ``rosters``: ``player_id`` -> ``gsis_id`` and ``team_id`` -> ``team``.
- ``team_stats_weekly``: ``team_id`` -> ``team``.

``core/player_stats.py`` is unaffected (the upstream stat tables already use
``player_id`` and ``team`` since v1.0; ``team`` was always tolerated by that
loader because the inline ``_opt('team_id', ...)`` path treats absence as a
NULL projection rather than a missing-required failure).

The registry is keyed on ``slice_key`` (not ``adapter_id``) so cross-check
stages share the same alias map as the corresponding primary slice. That
matches the convention in :mod:`new_nfl.adapters.slices`, where every Tier-A
primary and its Tier-B cross-check use the same ``slice_key``.

T3.1S design choice: in-place ``ALTER TABLE ... RENAME COLUMN`` instead of a
view layer or a SELECT-list rename. Rationale: the rename persists across
re-runs, the rest of the loader SQL stays unchanged, and the cross-check
``_detect_conflicts`` joins continue to use the canonical column names
without per-slice branching.

Future drifts add one entry to ``ALIAS_REGISTRY`` and one regression test.
No loader edit needed.
"""
from __future__ import annotations

import duckdb

# slice_key -> {upstream_name: canonical_name}.
#
# Keep entries lower-case on both sides; the helper compares case-insensitive
# and uses the original-case column name for the ALTER TABLE statement.
ALIAS_REGISTRY: dict[str, dict[str, str]] = {
    "players": {
        "gsis_id": "player_id",
    },
    "rosters": {
        "gsis_id": "player_id",
        "team": "team_id",
    },
    "team_stats_weekly": {
        "team": "team_id",
    },
}


def get_aliases_for_slice(slice_key: str) -> dict[str, str]:
    """Return the alias map for *slice_key*, or an empty dict when none."""
    return dict(ALIAS_REGISTRY.get(slice_key, {}))


def apply_column_aliases(
    con: duckdb.DuckDBPyConnection,
    qualified_table: str,
    slice_key: str,
) -> dict[str, str]:
    """Rename upstream columns to canonical names on *qualified_table*.

    Runs ``ALTER TABLE ... RENAME COLUMN`` for every alias whose upstream
    name is present and whose canonical name is absent on the table. The
    operation is idempotent: a second invocation observes the canonical
    name already in place and is a no-op.

    Returns the ``{upstream: canonical}`` map that was actually applied.

    No-op cases:
    - The slice has no aliases registered.
    - The table does not exist (defensive: cross-check stages may not yet
      be loaded; the caller should not have to know).
    - The upstream column is absent (already renamed, or never present).
    - The canonical column already exists (some other path renamed first).
    """
    mapping = ALIAS_REGISTRY.get(slice_key)
    if not mapping:
        return {}
    try:
        rows = con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return {}
    columns_by_lower: dict[str, str] = {
        str(row[0]).strip().lower(): str(row[0]).strip() for row in rows
    }
    applied: dict[str, str] = {}
    for upstream, canonical in mapping.items():
        upstream_lower = upstream.lower()
        canonical_lower = canonical.lower()
        if upstream_lower not in columns_by_lower:
            continue
        if canonical_lower in columns_by_lower:
            continue
        original_name = columns_by_lower[upstream_lower]
        con.execute(
            f'ALTER TABLE {qualified_table} '
            f'RENAME COLUMN "{original_name}" TO "{canonical}"'
        )
        applied[upstream] = canonical
        del columns_by_lower[upstream_lower]
        columns_by_lower[canonical_lower] = canonical
    return applied


__all__ = [
    "ALIAS_REGISTRY",
    "apply_column_aliases",
    "get_aliases_for_slice",
]
