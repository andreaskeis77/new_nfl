"""CLI-Plugins für T2.7E-Hardening-Commands (ADR-0033 Stream C).

Bündelt drei Operator-Surfaces unter einem Plugin-Modul:

* ``new-nfl trim-run-events --older-than 30d [--dry-run]`` — T2.7E-1
* ``new-nfl adapter-slice-sync`` — T2.7E-4 (manueller Projektions-Trigger)
* ``new-nfl dedupe-review-resolve --review-id ID --action {merge|reject|defer}
  [--notes TEXT]`` — T2.7E-5

Jeder Command ist ein eigener :class:`CliPlugin`; Registrierung passiert
beim Import. Die Module bleiben importfrei zueinander — ein kaputter
Dispatch in einem Command zieht die anderen nicht mit.
"""
from __future__ import annotations

import argparse

from new_nfl.cli_plugins import CliPlugin, register_cli_plugin

# ---------------------------------------------------------------------------
# trim-run-events  (T2.7E-1)
# ---------------------------------------------------------------------------


def _register_trim_run_events(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "trim-run-events",
        help=(
            "Delete meta.run_event + meta.run_artifact rows of completed "
            "runs older than <N> days (T2.7E-1)"
        ),
    )
    parser.add_argument(
        "--older-than",
        default="30d",
        help="Retention window, '<N>' or '<N>d' (default: 30d)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count candidates only; do not delete",
    )
    return parser


def _dispatch_trim_run_events(args: argparse.Namespace) -> int:
    from new_nfl.bootstrap import bootstrap_local_environment
    from new_nfl.meta.retention import parse_older_than, trim_run_events
    from new_nfl.settings import load_settings

    try:
        days = parse_older_than(args.older_than)
    except ValueError as exc:
        print(f"ERROR={exc}")
        return 2

    settings = load_settings()
    bootstrap_local_environment(settings)
    result = trim_run_events(
        settings, older_than_days=days, dry_run=bool(args.dry_run)
    )
    print(f"OLDER_THAN_DAYS={result.older_than_days}")
    print(f"DRY_RUN={'true' if result.dry_run else 'false'}")
    print(f"ELIGIBLE_RUN_COUNT={result.eligible_run_count}")
    print(f"DELETED_EVENT_COUNT={result.deleted_event_count}")
    print(f"DELETED_ARTIFACT_COUNT={result.deleted_artifact_count}")
    return 0


register_cli_plugin(
    CliPlugin(
        name="trim-run-events",
        register_parser=_register_trim_run_events,
        dispatch=_dispatch_trim_run_events,
    )
)


__all__: list[str] = []
