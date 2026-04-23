"""Runtime-Projektion der SLICE_REGISTRY nach meta.adapter_slice (T2.7E-4)."""
from __future__ import annotations

import pytest

from new_nfl._db import connect
from new_nfl.adapters.slices import SLICE_REGISTRY
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.meta.adapter_slice_registry import (
    AdapterSliceSyncResult,
    sync_adapter_slices,
)
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import load_settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD", "1")
    return load_settings()


def _count_adapter_slice(settings) -> int:
    con = connect(settings)
    try:
        row = con.execute("SELECT COUNT(*) FROM meta.adapter_slice").fetchone()
    finally:
        con.close()
    return int(row[0])


def _fetch_slice(settings, adapter_slice_id: str):
    con = connect(settings)
    try:
        row = con.execute(
            """
            SELECT adapter_id, slice_key, label, remote_url,
                   stage_target_object, core_table, mart_key, tier_role, notes
            FROM meta.adapter_slice WHERE adapter_slice_id = ?
            """,
            [adapter_slice_id],
        ).fetchone()
    finally:
        con.close()
    return row


def test_sync_projects_all_registry_slices(settings):
    ensure_metadata_surface(settings)
    result = sync_adapter_slices(settings)
    assert isinstance(result, AdapterSliceSyncResult)
    assert result.registry_slice_count == len(SLICE_REGISTRY)
    assert result.upserted_count == len(SLICE_REGISTRY)
    assert result.deleted_orphan_count == 0
    assert _count_adapter_slice(settings) == len(SLICE_REGISTRY)


def test_sync_is_idempotent(settings):
    ensure_metadata_surface(settings)
    sync_adapter_slices(settings)
    initial_count = _count_adapter_slice(settings)
    second = sync_adapter_slices(settings)
    assert _count_adapter_slice(settings) == initial_count
    assert second.deleted_orphan_count == 0


def test_sync_deletes_orphan_rows(settings):
    """Rows whose adapter_slice_id is not in SLICE_REGISTRY must be removed."""
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.adapter_slice (
                adapter_slice_id, adapter_id, slice_key, label, remote_url,
                stage_target_object, core_table, mart_key, tier_role, notes
            ) VALUES (
                'ghost::dropped', 'ghost', 'dropped',
                'Slice removed from registry', '', '', '', '', 'primary', ''
            )
            """
        )
    finally:
        con.close()

    result = sync_adapter_slices(settings)
    assert result.deleted_orphan_count == 1
    assert _fetch_slice(settings, "ghost::dropped") is None


def test_sync_updates_existing_row_fields(settings):
    """Pre-existing row with a stale label must be overwritten with the registry value."""
    ensure_metadata_surface(settings)
    first = next(iter(SLICE_REGISTRY.values()))
    slice_id = f"{first.adapter_id}::{first.slice_key}"
    con = connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.adapter_slice (
                adapter_slice_id, adapter_id, slice_key, label, remote_url,
                stage_target_object, core_table, mart_key, tier_role, notes
            ) VALUES (?, ?, ?, 'STALE LABEL', '', '', '', '', 'primary', '')
            """,
            [slice_id, first.adapter_id, first.slice_key],
        )
    finally:
        con.close()

    sync_adapter_slices(settings)
    row = _fetch_slice(settings, slice_id)
    assert row is not None
    assert row[2] == first.label


def test_bootstrap_auto_syncs_adapter_slice(settings):
    bootstrap_local_environment(settings)
    assert _count_adapter_slice(settings) == len(SLICE_REGISTRY)


def test_bootstrap_repeat_does_not_accumulate_rows(settings):
    bootstrap_local_environment(settings)
    bootstrap_local_environment(settings)
    bootstrap_local_environment(settings)
    assert _count_adapter_slice(settings) == len(SLICE_REGISTRY)
