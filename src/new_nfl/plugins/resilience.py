"""CLI-Plugins für T2.7C/T2.7D Resilience-Commands (ADR-0033 Stream B).

Bündelt vier Operator-Surfaces unter einem Plugin-Modul:

* ``new-nfl backup-snapshot --target PATH.zip`` — T2.7C
* ``new-nfl restore-snapshot --source PATH.zip --target DIR`` — T2.7C
* ``new-nfl verify-snapshot --source PATH.zip`` — T2.7C
* ``new-nfl replay-domain --domain DOMAIN [--source-file-id ID] [--dry-run]``
  — T2.7D

Jeder Command ist ein eigenes :class:`CliPlugin`; Registrierung passiert
beim Import. Die Module bleiben importfrei zueinander — ein kaputter
Dispatch in einem Command zieht die anderen nicht mit.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from new_nfl.cli_plugins import CliPlugin, register_cli_plugin

# ---------------------------------------------------------------------------
# backup-snapshot  (T2.7C)
# ---------------------------------------------------------------------------


def _register_backup_snapshot(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "backup-snapshot",
        help=(
            "Produce a verifiable ZIP snapshot of the DuckDB file and "
            "data/raw/ tree (T2.7C)"
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Destination ZIP path (parent dirs are created if missing)",
    )
    return parser


def _dispatch_backup_snapshot(args: argparse.Namespace) -> int:
    from new_nfl.bootstrap import bootstrap_local_environment
    from new_nfl.resilience.backup import backup_snapshot
    from new_nfl.settings import load_settings

    settings = load_settings()
    bootstrap_local_environment(settings)

    target = Path(args.target)
    result = backup_snapshot(settings, target)
    manifest = result.manifest
    print(f"TARGET_ZIP={result.target_zip}")
    print(f"RAW_FILE_COUNT={result.raw_file_count}")
    print(f"SCHEMA_VERSION={manifest.schema_version}")
    print(f"CREATED_AT={manifest.created_at}")
    print(f"DUCKDB_VERSION={manifest.duckdb_version}")
    print(f"DB_FILENAME={manifest.db_filename}")
    print(f"PAYLOAD_HASH={manifest.payload_hash}")
    print(f"FILE_HASH_COUNT={len(manifest.file_hashes)}")
    print(f"MART_TABLE_COUNT={len(manifest.row_counts)}")
    return 0


register_cli_plugin(
    CliPlugin(
        name="backup-snapshot",
        register_parser=_register_backup_snapshot,
        dispatch=_dispatch_backup_snapshot,
    )
)


# ---------------------------------------------------------------------------
# restore-snapshot  (T2.7C)
# ---------------------------------------------------------------------------


def _register_restore_snapshot(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "restore-snapshot",
        help=(
            "Extract and integrity-check a backup ZIP into a target "
            "directory (T2.7C)"
        ),
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the backup ZIP produced by backup-snapshot",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Empty target directory; created if missing",
    )
    return parser


def _dispatch_restore_snapshot(args: argparse.Namespace) -> int:
    from new_nfl.resilience.restore import (
        RestoreIntegrityError,
        restore_snapshot,
    )

    source = Path(args.source)
    target = Path(args.target)
    try:
        result = restore_snapshot(source, target)
    except RestoreIntegrityError as exc:
        print(f"ERROR={exc}")
        return 2

    print(f"SOURCE_ZIP={result.source_zip}")
    print(f"TARGET_DIR={result.target_dir}")
    print(f"DB_PATH={result.db_path}")
    print(f"RAW_ROOT={result.raw_root}")
    print(f"RESTORED_FILE_COUNT={result.restored_file_count}")
    print(f"SCHEMA_VERSION={result.manifest.schema_version}")
    print(f"PAYLOAD_HASH={result.manifest.payload_hash}")
    return 0


register_cli_plugin(
    CliPlugin(
        name="restore-snapshot",
        register_parser=_register_restore_snapshot,
        dispatch=_dispatch_restore_snapshot,
    )
)


# ---------------------------------------------------------------------------
# verify-snapshot  (T2.7C)
# ---------------------------------------------------------------------------


def _register_verify_snapshot(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "verify-snapshot",
        help=(
            "Verify manifest + per-entry SHA-256 of a backup ZIP without "
            "extracting to disk (T2.7C)"
        ),
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the backup ZIP produced by backup-snapshot",
    )
    return parser


def _dispatch_verify_snapshot(args: argparse.Namespace) -> int:
    from new_nfl.resilience.verify import VerifyError, verify_snapshot

    source = Path(args.source)
    try:
        result = verify_snapshot(source)
    except VerifyError as exc:
        print(f"ERROR={exc}")
        return 2

    print(f"SOURCE_ZIP={result.source_zip}")
    print(f"OK={'true' if result.ok else 'false'}")
    if result.manifest is not None:
        print(f"SCHEMA_VERSION={result.manifest.schema_version}")
        print(f"PAYLOAD_HASH={result.manifest.payload_hash}")
    print(f"MISSING_ENTRY_COUNT={len(result.missing_entries)}")
    print(f"HASH_MISMATCH_COUNT={len(result.hash_mismatches)}")
    print(f"UNEXPECTED_ENTRY_COUNT={len(result.unexpected_entries)}")
    for name in result.missing_entries:
        print(f"MISSING={name}")
    for name in result.hash_mismatches:
        print(f"MISMATCH={name}")
    for name in result.unexpected_entries:
        print(f"UNEXPECTED={name}")
    return 0 if result.ok else 2


register_cli_plugin(
    CliPlugin(
        name="verify-snapshot",
        register_parser=_register_verify_snapshot,
        dispatch=_dispatch_verify_snapshot,
    )
)


# ---------------------------------------------------------------------------
# replay-domain  (T2.7D)
# ---------------------------------------------------------------------------


def _register_replay_domain(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    from new_nfl.resilience.replay import DOMAIN_SPECS

    parser = subparsers.add_parser(
        "replay-domain",
        help=(
            "Snapshot core.<domain>, re-run the core loader and diff "
            "pre-state against post-state (T2.7D)"
        ),
    )
    parser.add_argument(
        "--domain",
        required=True,
        choices=sorted(DOMAIN_SPECS),
        help="Canonical core domain to replay",
    )
    parser.add_argument(
        "--source-file-id",
        default=None,
        help=(
            "Optional provenance tag — carried through the report so an "
            "operator can trace which stage run triggered the drill"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report pre-state row count only; do not mutate the live DB",
    )
    return parser


def _dispatch_replay_domain(args: argparse.Namespace) -> int:
    from new_nfl.bootstrap import bootstrap_local_environment
    from new_nfl.resilience.replay import replay_domain
    from new_nfl.settings import load_settings

    settings = load_settings()
    bootstrap_local_environment(settings)

    try:
        result = replay_domain(
            settings,
            domain=args.domain,
            source_file_id=args.source_file_id,
            dry_run=bool(args.dry_run),
        )
    except ValueError as exc:
        print(f"ERROR={exc}")
        return 2

    print(f"DOMAIN={result.domain}")
    print(f"CORE_TABLE={result.core_table}")
    print(f"SOURCE_FILE_ID={result.source_file_id or ''}")
    print(f"DRY_RUN={'true' if result.dry_run else 'false'}")
    print(f"PRE_ROW_COUNT={result.pre_row_count}")
    print(f"POST_ROW_COUNT={result.post_row_count}")

    if result.dry_run or result.diff is None:
        for note in result.notes:
            print(f"NOTE={note}")
        return 0

    summary = result.diff.summary()
    print(f"DIFF_ONLY_IN_A={summary['only_in_a']}")
    print(f"DIFF_ONLY_IN_B={summary['only_in_b']}")
    print(f"DIFF_CHANGED={summary['changed']}")
    print(
        "IS_DETERMINISTIC="
        f"{'true' if result.is_deterministic else 'false'}"
    )
    return 0 if result.is_deterministic else 2


register_cli_plugin(
    CliPlugin(
        name="replay-domain",
        register_parser=_register_replay_domain,
        dispatch=_dispatch_replay_domain,
    )
)


__all__: list[str] = []
