"""Tests for ``backup_snapshot`` (T2.7C).

The fixture builds a minimal settings tree (empty DuckDB + two tiny raw
files) so the archive stays in the kilobyte range. The determinism test
builds two archives from byte-identical inputs and asserts that the
manifest's ``payload_hash`` is stable — ZIP entry timestamps and
compressed sizes may legitimately vary, but the payload cannot.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import duckdb
import pytest

from new_nfl.resilience.backup import (
    DB_ARCHIVE_DIR,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    RAW_ARCHIVE_DIR,
    backup_snapshot,
)
from new_nfl.resilience.verify import VerifyError, verify_snapshot
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
            """
            CREATE OR REPLACE TABLE mart.probe_v1 (
                id VARCHAR,
                value VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO mart.probe_v1 VALUES (?, ?)",
            [("a", "alpha"), ("b", "beta")],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _seed_raw_files(settings: Settings) -> None:
    raw = settings.raw_root
    (raw / "nflverse_bulk").mkdir(parents=True, exist_ok=True)
    (raw / "nflverse_bulk" / "teams.csv").write_bytes(
        b"team_id,team_name\nBUF,Buffalo\nMIA,Miami\n"
    )
    (raw / "nflverse_bulk" / "meta.json").write_bytes(b'{"season":2024}')


def test_backup_produces_zip_with_manifest_and_known_layout(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    _seed_raw_files(settings)

    target = tmp_path / "snap.zip"
    result = backup_snapshot(settings, target)

    assert target.exists()
    assert result.target_zip == target
    assert result.raw_file_count == 2

    with zipfile.ZipFile(target, "r") as zf:
        names = set(zf.namelist())
        assert MANIFEST_FILENAME in names
        assert any(n.startswith(f"{DB_ARCHIVE_DIR}/") for n in names)
        assert any(n.startswith(f"{RAW_ARCHIVE_DIR}/") for n in names)
        raw_manifest = zf.read(MANIFEST_FILENAME).decode("utf-8")

    manifest = json.loads(raw_manifest)
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["db_filename"] == settings.db_path.name
    assert "payload_hash" in manifest
    assert "created_at" in manifest
    assert "duckdb_version" in manifest


def test_backup_uses_forward_slashes_in_archive_paths(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    (settings.raw_root / "nested" / "deep").mkdir(parents=True)
    (settings.raw_root / "nested" / "deep" / "note.txt").write_text("ok")

    target = tmp_path / "snap.zip"
    backup_snapshot(settings, target)

    with zipfile.ZipFile(target, "r") as zf:
        names = zf.namelist()
    for name in names:
        assert "\\" not in name, f"archive path uses backslash: {name}"


def test_backup_includes_per_file_sha256_in_manifest(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    _seed_raw_files(settings)
    target = tmp_path / "snap.zip"

    result = backup_snapshot(settings, target)

    hashes = result.manifest.file_hashes
    assert f"{DB_ARCHIVE_DIR}/{settings.db_path.name}" in hashes
    assert f"{RAW_ARCHIVE_DIR}/nflverse_bulk/teams.csv" in hashes
    for h in hashes.values():
        assert len(h) == 64  # SHA-256 hex digest
        int(h, 16)  # must be hex-parseable


def test_backup_includes_mart_row_counts(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    target = tmp_path / "snap.zip"

    result = backup_snapshot(settings, target)
    assert result.manifest.row_counts.get("mart.probe_v1") == 2


def test_backup_is_payload_deterministic_across_two_runs(
    settings: Settings, tmp_path: Path
) -> None:
    """Same input bytes → same ``payload_hash``.

    ZIP entry metadata (mtime, compressed size) may vary between runs —
    only the payload fields of the manifest are required to be stable.
    """
    _seed_tiny_db(settings)
    _seed_raw_files(settings)

    target_a = tmp_path / "a.zip"
    target_b = tmp_path / "b.zip"

    result_a = backup_snapshot(settings, target_a)
    # Second backup of the identical inputs.
    result_b = backup_snapshot(settings, target_b)

    assert result_a.manifest.payload_hash == result_b.manifest.payload_hash
    assert result_a.manifest.file_hashes == result_b.manifest.file_hashes
    assert result_a.manifest.row_counts == result_b.manifest.row_counts


def test_backup_succeeds_with_empty_raw_tree(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    # raw_root exists but is empty
    target = tmp_path / "snap.zip"

    result = backup_snapshot(settings, target)
    assert result.raw_file_count == 0
    # Only the DB entry should be in the manifest.
    assert any(
        k.startswith(f"{DB_ARCHIVE_DIR}/") for k in result.manifest.file_hashes
    )
    assert not any(
        k.startswith(f"{RAW_ARCHIVE_DIR}/")
        for k in result.manifest.file_hashes
    )


def test_backup_succeeds_when_raw_root_missing(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    shutil.rmtree(settings.raw_root)
    target = tmp_path / "snap.zip"

    result = backup_snapshot(settings, target)
    assert result.raw_file_count == 0


def test_backup_creates_target_parent_directory(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    nested_target = tmp_path / "out" / "drills" / "snap.zip"

    result = backup_snapshot(settings, nested_target)
    assert nested_target.exists()
    assert result.target_zip == nested_target


# ---------------------------------------------------------------------------
# Verify-snapshot — integrity check without extracting to disk.
# ---------------------------------------------------------------------------


def test_verify_passes_on_fresh_backup(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    _seed_raw_files(settings)
    target = tmp_path / "snap.zip"
    backup_snapshot(settings, target)

    result = verify_snapshot(target)
    assert result.ok
    assert result.manifest is not None
    assert result.hash_mismatches == ()
    assert result.missing_entries == ()
    assert result.unexpected_entries == ()


def test_verify_detects_tampered_entry(
    settings: Settings, tmp_path: Path
) -> None:
    _seed_tiny_db(settings)
    _seed_raw_files(settings)
    good = tmp_path / "good.zip"
    backup_snapshot(settings, good)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(good, "r") as src, zipfile.ZipFile(
        tampered, "w"
    ) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == f"{RAW_ARCHIVE_DIR}/nflverse_bulk/teams.csv":
                data = b"TAMPERED,line\n"
            dst.writestr(item, data)

    result = verify_snapshot(tampered)
    assert not result.ok
    assert result.hash_mismatches
    assert (
        f"{RAW_ARCHIVE_DIR}/nflverse_bulk/teams.csv"
        in result.hash_mismatches
    )


def test_verify_reports_missing_entry_vs_manifest(tmp_path: Path) -> None:
    """Manifest declares a file that is absent from the archive."""
    bad = tmp_path / "bad.zip"
    manifest = {
        "schema_version": "1",
        "created_at": "2026-04-23T00:00:00+00:00",
        "duckdb_version": "1.5.1",
        "db_filename": "new_nfl.duckdb",
        "file_hashes": {
            "db/new_nfl.duckdb": "0" * 64,
            "raw/ghost.txt": "0" * 64,
        },
        "row_counts": {},
        "payload_hash": "0" * 64,
    }
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr(MANIFEST_FILENAME, json.dumps(manifest))
        zf.writestr("db/new_nfl.duckdb", b"\x00")

    result = verify_snapshot(bad)
    assert not result.ok
    assert "raw/ghost.txt" in result.missing_entries


def test_verify_raises_on_non_zip(tmp_path: Path) -> None:
    not_zip = tmp_path / "not.zip"
    not_zip.write_bytes(b"not a zip")
    with pytest.raises(VerifyError, match="not a valid ZIP"):
        verify_snapshot(not_zip)


def test_verify_raises_when_source_missing(tmp_path: Path) -> None:
    with pytest.raises(VerifyError, match="not found"):
        verify_snapshot(tmp_path / "ghost.zip")


def test_verify_raises_on_archive_without_manifest(tmp_path: Path) -> None:
    bad = tmp_path / "no_manifest.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("db/new_nfl.duckdb", b"\x00")
    with pytest.raises(VerifyError, match="missing manifest"):
        verify_snapshot(bad)
