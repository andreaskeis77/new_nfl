"""Verify a backup snapshot without performing a restore (T2.7C).

Streams archive entries and compares per-entry SHA-256 against the
manifest. Useful for periodic integrity sweeps on an existing archive
store — the restore cost is not paid, so the operation is cheap enough
to run on a schedule.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from new_nfl.resilience.backup import MANIFEST_FILENAME, BackupManifest


class VerifyError(Exception):
    """Raised when the archive is structurally unreadable.

    A hash mismatch on an otherwise-readable archive is *not* an exception
    — it's reflected in the returned :class:`VerifyResult` with ``ok=False``
    so the CLI can render a readable report.
    """


@dataclass(frozen=True)
class VerifyResult:
    source_zip: Path
    ok: bool
    manifest: BackupManifest | None
    missing_entries: tuple[str, ...] = field(default_factory=tuple)
    hash_mismatches: tuple[str, ...] = field(default_factory=tuple)
    unexpected_entries: tuple[str, ...] = field(default_factory=tuple)


def _stream_sha256(zf: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with zf.open(name, mode="r") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_snapshot(source_zip: Path) -> VerifyResult:
    """Validate archive integrity against the embedded manifest.

    Never extracts to disk — each entry is hashed as it streams out of
    the ZIP. Returns a structured report with every mismatch located so
    the caller can print a full diagnostic.
    """
    source_zip = Path(source_zip)

    if not source_zip.exists():
        raise VerifyError(f"snapshot not found: {source_zip}")
    if not zipfile.is_zipfile(source_zip):
        raise VerifyError(
            f"source is not a valid ZIP archive: {source_zip}"
        )

    with zipfile.ZipFile(source_zip, mode="r") as zf:
        try:
            raw = zf.read(MANIFEST_FILENAME)
        except KeyError as exc:
            raise VerifyError(
                f"snapshot missing {MANIFEST_FILENAME}"
            ) from exc
        try:
            data = json.loads(raw.decode("utf-8"))
            manifest = BackupManifest.from_dict(data)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise VerifyError(
                f"{MANIFEST_FILENAME} is not a valid manifest: {exc}"
            ) from exc

        names_in_zip = set(zf.namelist())
        declared = set(manifest.file_hashes)

        missing = sorted(declared - names_in_zip)
        unexpected = sorted(
            n for n in (names_in_zip - declared) if n != MANIFEST_FILENAME
        )

        mismatches: list[str] = []
        for name in sorted(declared & names_in_zip):
            actual = _stream_sha256(zf, name)
            if actual != manifest.file_hashes[name]:
                mismatches.append(name)

    ok = not (missing or mismatches or unexpected)

    return VerifyResult(
        source_zip=source_zip,
        ok=ok,
        manifest=manifest,
        missing_entries=tuple(missing),
        hash_mismatches=tuple(mismatches),
        unexpected_entries=tuple(unexpected),
    )


__all__ = [
    "VerifyError",
    "VerifyResult",
    "verify_snapshot",
]
