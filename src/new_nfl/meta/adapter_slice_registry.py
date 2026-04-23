"""Runtime-Projektion der Code-``SLICE_REGISTRY`` nach ``meta.adapter_slice`` (T2.7E-4).

Die Read-Side (CLI ``list-slices``, UI ``mart.*``-Drill-Downs, Debug-SQL
direkt auf DuckDB) arbeitet bisher nur mit der im Python-Code lebenden
``SLICE_REGISTRY`` aus :mod:`new_nfl.adapters.slices`. Das zwingt
externe Verbraucher (BI-Tools, ad-hoc-Notebooks) dazu, das Python-Modul
zu importieren, nur um zu wissen, welche Slices existieren.

Dieser Sync spiegelt die Registry als Tabelle ``meta.adapter_slice`` in
DuckDB. Die Projektion ist voll rebuildbar:

1. :func:`sync_adapter_slices` liest :data:`SLICE_REGISTRY`,
2. löscht alle Zeilen mit ``adapter_slice_id``, die nicht mehr im Code
   existieren (Drift-Schutz),
3. schreibt jede aktuelle Zeile per DELETE+INSERT neu (inkl.
   ``synced_at = CURRENT_TIMESTAMP``).

Aufrufer: :func:`new_nfl.bootstrap.bootstrap_local_environment`
(best-effort beim Start) und die CLI ``new-nfl adapter-slice-sync``
(manueller Trigger).

Idempotent: ein zweiter Lauf über eine unveränderte Registry schreibt
dieselben Werte mit neuem ``synced_at`` — keine strukturellen Änderungen.
"""
from __future__ import annotations

from dataclasses import dataclass

from new_nfl._db import connect
from new_nfl.adapters.slices import SLICE_REGISTRY, SliceSpec
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings


@dataclass(frozen=True)
class AdapterSliceSyncResult:
    registry_slice_count: int
    upserted_count: int
    deleted_orphan_count: int


def _slice_id(spec: SliceSpec) -> str:
    return f"{spec.adapter_id}::{spec.slice_key}"


def sync_adapter_slices(settings: Settings) -> AdapterSliceSyncResult:
    """Project :data:`SLICE_REGISTRY` into ``meta.adapter_slice``.

    Full rebuild: orphan rows (slices removed from code) are deleted;
    every current slice is replaced with the current field values and a
    fresh ``synced_at`` timestamp.
    """
    ensure_metadata_surface(settings)
    specs: list[SliceSpec] = list(SLICE_REGISTRY.values())
    current_ids = {_slice_id(spec) for spec in specs}

    con = connect(settings)
    try:
        if current_ids:
            placeholders = ", ".join("?" * len(current_ids))
            orphan_row = con.execute(
                f"""
                SELECT COUNT(*) FROM meta.adapter_slice
                WHERE adapter_slice_id NOT IN ({placeholders})
                """,
                list(current_ids),
            ).fetchone()
            deleted_orphan_count = int(orphan_row[0]) if orphan_row else 0
            con.execute(
                f"""
                DELETE FROM meta.adapter_slice
                WHERE adapter_slice_id NOT IN ({placeholders})
                """,
                list(current_ids),
            )
        else:
            orphan_row = con.execute(
                "SELECT COUNT(*) FROM meta.adapter_slice"
            ).fetchone()
            deleted_orphan_count = int(orphan_row[0]) if orphan_row else 0
            con.execute("DELETE FROM meta.adapter_slice")

        upserted = 0
        for spec in specs:
            slice_id = _slice_id(spec)
            con.execute(
                "DELETE FROM meta.adapter_slice WHERE adapter_slice_id = ?",
                [slice_id],
            )
            con.execute(
                """
                INSERT INTO meta.adapter_slice (
                    adapter_slice_id, adapter_id, slice_key, label,
                    remote_url, stage_target_object, core_table, mart_key,
                    tier_role, notes, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    slice_id,
                    spec.adapter_id,
                    spec.slice_key,
                    spec.label,
                    spec.remote_url,
                    spec.stage_target_object,
                    spec.core_table,
                    spec.mart_key,
                    spec.tier_role,
                    spec.notes,
                ],
            )
            upserted += 1
    finally:
        con.close()

    return AdapterSliceSyncResult(
        registry_slice_count=len(specs),
        upserted_count=upserted,
        deleted_orphan_count=deleted_orphan_count,
    )


def try_sync_adapter_slices(settings: Settings) -> None:
    """Best-effort wrapper for the bootstrap path.

    Bootstrap must never fail because of adapter_slice-sync side effects;
    exceptions are swallowed (the explicit CLI
    ``new-nfl adapter-slice-sync`` surfaces the same call loudly).
    """
    try:
        sync_adapter_slices(settings)
    except Exception:
        return


__all__ = [
    "AdapterSliceSyncResult",
    "sync_adapter_slices",
    "try_sync_adapter_slices",
]
