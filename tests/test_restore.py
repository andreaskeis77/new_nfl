"""Tests for ``restore_snapshot`` (T2.7C).

The happy path builds a backup, extracts it into a fresh directory and
runs a tiny smoke query against the restored DuckDB to prove the archive
carries usable data. The failure paths cover corrupted archives,
missing manifests and tampered entries.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import duckdb
import pytest

from new_nfl.resilience.backup import (
    DB_ARCHIVE_DIR,
    MANIFEST_FILENAME,
    RAW_ARCHIVE_DIR,
    backup_snapshot,
)
from new_nfl.resilience.restore import (
    RestoreIntegrityError,
    restore_snapshot,
)
from new_nfl.settings import Settings


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    db_path = data_root / "db" / "new_nfl.duckdb"
    repo_root.mkdir(parents=True, exist_ok=True)
    (data_root / "raw").mkdir(parents=True, exist_ok=True)
    return Settings(
        repo_root=repo_root,
        env="test",
        data_root=data_root,
        db_path=db_path,
    )


def _seed_tiny_db(settings: Settings) -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            "CREATE OR REPLACE TABLE mart.probe_v1 (id VARCHAR, value VARCHAR)"
        )
        con.executemany(
            "INSERT INTO mart.probe_v1 VALUES (?, ?)",
            [("a", "alpha"), ("b", "beta"), ("c", "gamma")],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _make_backup(settings: Settings, tmp_path: Path) -> Path:
    target = tmp_path / "snap.zip"
    (settings.raw_root / "probe.txt").write_text("hello", encoding="utf-8")
    _seed_tiny_db(settings)
    backup_snapshot(settings, target)
    return target


def test_restore_reconstructs_db_and_raw_layout(
    settings: Settings, tmp_path: Path
) -> None:
    snap = _make_backup(settings, tmp_path)

    target_dir = tmp_path / "restored"
    result = restore_snapshot(snap, target_dir)

    assert result.db_path.exists()
    assert result.raw_root.exists()
    assert (result.raw_root / "probe.txt").read_text(encoding="utf-8") == "hello"
    assert result.target_dir == target_dir


def test_restore_smoke_query_returns_expected_row_count(
    settings: Settings, tmp_path: Path
) -> None:
    """Smoke: after restore, a tiny query on the restored DB succeeds."""
    snap = _make_backup(settings, tmp_path)
    target_dir = tmp_path / "restored"
    result = restore_snapshot(snap, target_dir)

    con = duckdb.connect(str(result.db_path))
    try:
        count = con.execute("SELECT COUNT(*) FROM mart.probe_v1").fetchone()[0]
    finally:
        con.close()
    assert int(count) == 3


def test_restore_raises_on_non_zip_source(tmp_path: Path) -> None:
    not_a_zip = tmp_path / "bogus.zip"
    not_a_zip.write_text("not a zip file", encoding="utf-8")

    with pytest.raises(RestoreIntegrityError, match="not a valid ZIP"):
        restore_snapshot(not_a_zip, tmp_path / "restored")


def test_restore_raises_when_manifest_is_missing(tmp_path: Path) -> None:
    bad_zip = tmp_path / "no_manifest.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("db/new_nfl.duckdb", b"\x00")

    with pytest.raises(RestoreIntegrityError, match="missing manifest"):
        restore_snapshot(bad_zip, tmp_path / "restored")


def test_restore_raises_on_tampered_entry(
    settings: Settings, tmp_path: Path
) -> None:
    """Rebuild a backup with one entry overwritten — restore must reject it."""
    snap = _make_backup(settings, tmp_path)

    # Copy the archive contents to a new ZIP, overwriting one raw file.
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(snap, "r") as src, zipfile.ZipFile(
        tampered, "w"
    ) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == f"{RAW_ARCHIVE_DIR}/probe.txt":
                data = b"TAMPERED"
            dst.writestr(item, data)

    with pytest.raises(RestoreIntegrityError, match="manifest mismatch"):
        restore_snapshot(tampered, tmp_path / "restored")


def test_restore_raises_on_archive_with_unsafe_path(tmp_path: Path) -> None:
    bad_zip = tmp_path / "unsafe.zip"
    manifest = {
        "schema_version": "1",
        "created_at": "2026-04-23T00:00:00+00:00",
        "duckdb_version": "1.5.1",
        "db_filename": "new_nfl.duckdb",
        "file_hashes": {"../escape.txt": "0" * 64},
        "row_counts": {},
        "payload_hash": "0" * 64,
    }
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr(MANIFEST_FILENAME, json.dumps(manifest))
        zf.writestr("../escape.txt", b"oops")

    with pytest.raises(RestoreIntegrityError, match="unsafe path"):
        restore_snapshot(bad_zip, tmp_path / "restored")


def test_restore_creates_target_directory_if_missing(
    settings: Settings, tmp_path: Path
) -> None:
    snap = _make_backup(settings, tmp_path)
    target_dir = tmp_path / "does" / "not" / "exist"

    result = restore_snapshot(snap, target_dir)
    assert target_dir.is_dir()
    assert result.db_path.exists()


def test_restore_manifest_is_loaded_as_dataclass(
    settings: Settings, tmp_path: Path
) -> None:
    snap = _make_backup(settings, tmp_path)
    result = restore_snapshot(snap, tmp_path / "restored")
    assert result.manifest.schema_version == "1"
    assert result.manifest.db_filename == settings.db_path.name
    assert result.manifest.file_hashes
    db_key = f"{DB_ARCHIVE_DIR}/{settings.db_path.name}"
    assert db_key in result.manifest.file_hashes
