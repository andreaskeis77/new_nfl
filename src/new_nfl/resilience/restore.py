"""Restore a backup snapshot into an empty target directory (T2.7C).

Mirrors the archive layout produced by :mod:`new_nfl.resilience.backup`:

* ``<target_dir>/<db_filename>``
* ``<target_dir>/raw/...``

Performs integrity validation of the extracted files against the
manifest's ``file_hashes``. A mismatch raises :class:`RestoreIntegrityError`
so the CLI can convert it into a non-zero exit.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from new_nfl.resilience.backup import (
    DB_ARCHIVE_DIR,
    MANIFEST_FILENAME,
    RAW_ARCHIVE_DIR,
    BackupManifest,
)


class RestoreIntegrityError(Exception):
    """Raised when a restored file's hash does not match the manifest."""


@dataclass(frozen=True)
class RestoreResult:
    source_zip: Path
    target_dir: Path
    db_path: Path
    raw_root: Path
    manifest: BackupManifest
    restored_file_count: int
    extracted_paths: tuple[str, ...] = field(default_factory=tuple)


def _sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(zf: zipfile.ZipFile) -> BackupManifest:
    try:
        raw = zf.read(MANIFEST_FILENAME)
    except KeyError as exc:
        raise RestoreIntegrityError(
            f"snapshot missing {MANIFEST_FILENAME}"
        ) from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestoreIntegrityError(
            f"{MANIFEST_FILENAME} is not valid UTF-8 JSON: {exc}"
        ) from exc
    try:
        return BackupManifest.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise RestoreIntegrityError(
            f"{MANIFEST_FILENAME} is missing required fields: {exc}"
        ) from exc


def restore_snapshot(source_zip: Path, target_dir: Path) -> RestoreResult:
    """Extract ``source_zip`` into ``target_dir`` and verify file hashes.

    ``target_dir`` is created if missing. Existing contents are left in
    place but any archive entry that collides with an existing file will
    overwrite it. Integrity is verified after extraction — a mismatch
    raises :class:`RestoreIntegrityError`.
    """
    source_zip = Path(source_zip)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if not zipfile.is_zipfile(source_zip):
        raise RestoreIntegrityError(
            f"source is not a valid ZIP archive: {source_zip}"
        )

    extracted: list[str] = []
    with zipfile.ZipFile(source_zip, mode="r") as zf:
        manifest = _load_manifest(zf)
        for name in zf.namelist():
            if name == MANIFEST_FILENAME:
                continue
            # Guard against path traversal in the archive.
            normalised = Path(name)
            if normalised.is_absolute() or ".." in normalised.parts:
                raise RestoreIntegrityError(
                    f"archive contains unsafe path: {name}"
                )
            zf.extract(name, target_dir)
            extracted.append(name)

    db_archive_prefix = f"{DB_ARCHIVE_DIR}/"
    db_archive_name = f"{db_archive_prefix}{manifest.db_filename}"
    db_path = target_dir / DB_ARCHIVE_DIR / manifest.db_filename
    raw_root = target_dir / RAW_ARCHIVE_DIR

    # Verify every manifest entry. A missing or mismatched file is a hard
    # error — the operator should not silently run against a corrupted
    # restore.
    mismatches: list[str] = []
    missing: list[str] = []
    for archive_name, expected_hash in manifest.file_hashes.items():
        extracted_path = target_dir / Path(archive_name)
        if not extracted_path.exists():
            missing.append(archive_name)
            continue
        actual_hash = _sha256_of_file(extracted_path)
        if actual_hash != expected_hash:
            mismatches.append(archive_name)

    if missing or mismatches:
        raise RestoreIntegrityError(
            "manifest mismatch — "
            f"missing={sorted(missing)} mismatched={sorted(mismatches)}"
        )

    if db_archive_name not in manifest.file_hashes:
        raise RestoreIntegrityError(
            f"manifest does not reference {db_archive_name}"
        )

    return RestoreResult(
        source_zip=source_zip,
        target_dir=target_dir,
        db_path=db_path,
        raw_root=raw_root,
        manifest=manifest,
        restored_file_count=len(manifest.file_hashes),
        extracted_paths=tuple(extracted),
    )


__all__ = [
    "RestoreIntegrityError",
    "RestoreResult",
    "restore_snapshot",
]
