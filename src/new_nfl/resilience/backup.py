"""Backup snapshot for the DuckDB file + ``data/raw/`` tree (T2.7C).

The snapshot is a single ZIP containing:

* ``db/<db_filename>`` — a consistent copy of the DuckDB file after a
  ``CHECKPOINT`` and connection close
* ``raw/...`` — every file under ``settings.raw_root``, preserving the
  relative layout
* ``manifest.json`` — provenance and integrity metadata (schema version,
  UTC creation timestamp, duckdb library version, per-file SHA-256 and
  mart row counts)

Determinism contract: for the same input bytes the manifest ``file_hashes``
and ``row_counts`` are identical, and so is ``payload_hash``. ZIP
metadata (entry mtimes, compressed sizes) may legitimately differ, but
the *payload* is stable — that is what :mod:`new_nfl.resilience.verify`
checks against.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from new_nfl._db import connect
from new_nfl.settings import Settings

MANIFEST_FILENAME = "manifest.json"
DB_ARCHIVE_DIR = "db"
RAW_ARCHIVE_DIR = "raw"
MANIFEST_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class BackupManifest:
    schema_version: str
    created_at: str
    duckdb_version: str
    db_filename: str
    file_hashes: dict[str, str]
    row_counts: dict[str, int]
    payload_hash: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "created_at": self.created_at,
                "duckdb_version": self.duckdb_version,
                "db_filename": self.db_filename,
                "file_hashes": self.file_hashes,
                "row_counts": self.row_counts,
                "payload_hash": self.payload_hash,
            },
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupManifest:
        return cls(
            schema_version=str(data["schema_version"]),
            created_at=str(data["created_at"]),
            duckdb_version=str(data["duckdb_version"]),
            db_filename=str(data["db_filename"]),
            file_hashes={str(k): str(v) for k, v in data["file_hashes"].items()},
            row_counts={str(k): int(v) for k, v in data["row_counts"].items()},
            payload_hash=str(data["payload_hash"]),
        )


@dataclass(frozen=True)
class BackupResult:
    target_zip: Path
    manifest: BackupManifest
    raw_file_count: int
    included_paths: tuple[str, ...] = field(default_factory=tuple)


def _sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _collect_raw_files(raw_root: Path) -> list[Path]:
    if not raw_root.exists():
        return []
    return sorted(
        (p for p in raw_root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(raw_root).as_posix(),
    )


def _mart_row_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Row counts for every table under the ``mart`` schema.

    Missing schema (fresh DB, no mart built yet) simply returns an empty
    dict — we must not fail the backup because the operator has not yet
    run a mart build.
    """
    try:
        rows = con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'mart'
            ORDER BY table_name
            """
        ).fetchall()
    except duckdb.Error:
        return {}
    counts: dict[str, int] = {}
    for (name,) in rows:
        qualified = f"mart.{name}"
        try:
            count = int(con.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0])
        except duckdb.Error:
            continue
        counts[qualified] = count
    return counts


def _compute_payload_hash(
    schema_version: str,
    db_filename: str,
    file_hashes: dict[str, str],
    row_counts: dict[str, int],
) -> str:
    """Deterministic hash over the content-bearing fields of the manifest.

    Intentionally excludes ``created_at`` and ``duckdb_version`` — those
    are provenance, not payload. Two backups of identical bytes on the
    same schema_version yield the same payload_hash.
    """
    payload = json.dumps(
        {
            "schema_version": schema_version,
            "db_filename": db_filename,
            "file_hashes": dict(sorted(file_hashes.items())),
            "row_counts": dict(sorted(row_counts.items())),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _checkpoint_and_copy_db(settings: Settings, dest: Path) -> None:
    """Issue a ``CHECKPOINT`` then copy the DB file to ``dest``.

    Opening and closing the connection flushes DuckDB's WAL and write-lock
    — after ``con.close()`` the on-disk file is a consistent snapshot that
    can be copied safely. No running worker is assumed; if a concurrent
    writer holds the file, the copy may observe torn state and verify
    will later flag the hash mismatch.
    """
    if settings.db_path.exists():
        con = connect(settings)
        try:
            con.execute("CHECKPOINT")
        finally:
            con.close()
        shutil.copy2(settings.db_path, dest)
    else:
        # Fresh environment with no DB yet — create an empty placeholder so
        # the archive layout stays uniform.
        dest.touch()


def backup_snapshot(settings: Settings, target_zip: Path) -> BackupResult:
    """Produce a verifiable snapshot ZIP at ``target_zip``.

    The caller is responsible for closing any pooled DuckDB connections
    *before* calling this function. The backup itself opens and closes its
    own connection in a narrow critical section.
    """
    target_zip = Path(target_zip)
    target_zip.parent.mkdir(parents=True, exist_ok=True)

    raw_files = _collect_raw_files(settings.raw_root)
    db_filename = settings.db_path.name or "new_nfl.duckdb"

    with tempfile.TemporaryDirectory(prefix="new-nfl-backup-") as staging_str:
        staging = Path(staging_str)
        db_staged = staging / db_filename
        _checkpoint_and_copy_db(settings, db_staged)

        file_hashes: dict[str, str] = {}
        included: list[tuple[str, Path]] = []

        db_archive_name = f"{DB_ARCHIVE_DIR}/{db_filename}"
        file_hashes[db_archive_name] = _sha256_of_file(db_staged)
        included.append((db_archive_name, db_staged))

        for raw_file in raw_files:
            rel = raw_file.relative_to(settings.raw_root).as_posix()
            archive_name = f"{RAW_ARCHIVE_DIR}/{rel}"
            file_hashes[archive_name] = _sha256_of_file(raw_file)
            included.append((archive_name, raw_file))

        # Row counts come from the *staged* DB copy so we don't re-open the
        # live file after checkpoint. This keeps the manifest and payload
        # fully derived from what is about to be archived.
        staged_con = duckdb.connect(str(db_staged)) if db_staged.stat().st_size else None
        try:
            row_counts = _mart_row_counts(staged_con) if staged_con is not None else {}
        finally:
            if staged_con is not None:
                staged_con.close()

        payload_hash = _compute_payload_hash(
            MANIFEST_SCHEMA_VERSION, db_filename, file_hashes, row_counts
        )
        manifest = BackupManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            created_at=datetime.now(tz=UTC).isoformat(),
            duckdb_version=duckdb.__version__,
            db_filename=db_filename,
            file_hashes=file_hashes,
            row_counts=row_counts,
            payload_hash=payload_hash,
        )

        with zipfile.ZipFile(
            target_zip,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as zf:
            for archive_name, source in included:
                zf.write(source, arcname=archive_name)
            zf.writestr(MANIFEST_FILENAME, manifest.to_json())

    return BackupResult(
        target_zip=target_zip,
        manifest=manifest,
        raw_file_count=len(raw_files),
        included_paths=tuple(name for name, _ in included),
    )


__all__ = [
    "BackupManifest",
    "BackupResult",
    "DB_ARCHIVE_DIR",
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "RAW_ARCHIVE_DIR",
    "backup_snapshot",
]
