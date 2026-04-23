"""Resilience surface (T2.7C/D).

Backup/restore/verify for DuckDB + raw snapshots, and replay of core-load
domains against a pre-state snapshot. All four operator surfaces live as
CLI plugins (see :mod:`new_nfl.plugins.resilience`) registered via the
T2.7P CLI-plugin registry (ADR-0033). The core pipeline (runner, mart,
web) is not touched — resilience is a peripheral operator tool.
"""
from new_nfl.resilience.backup import (
    BackupManifest,
    BackupResult,
    backup_snapshot,
)
from new_nfl.resilience.diff import TableDiff, diff_tables
from new_nfl.resilience.replay import ReplayResult, replay_domain
from new_nfl.resilience.restore import RestoreResult, restore_snapshot
from new_nfl.resilience.verify import VerifyResult, verify_snapshot

__all__ = [
    "BackupManifest",
    "BackupResult",
    "ReplayResult",
    "RestoreResult",
    "TableDiff",
    "VerifyResult",
    "backup_snapshot",
    "diff_tables",
    "replay_domain",
    "restore_snapshot",
    "verify_snapshot",
]
