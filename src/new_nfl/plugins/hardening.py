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


# ---------------------------------------------------------------------------
# adapter-slice-sync  (T2.7E-4)
# ---------------------------------------------------------------------------


def _register_adapter_slice_sync(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "adapter-slice-sync",
        help=(
            "Project the code-level SLICE_REGISTRY into meta.adapter_slice "
            "(T2.7E-4)"
        ),
    )
    return parser


def _dispatch_adapter_slice_sync(args: argparse.Namespace) -> int:
    from new_nfl.bootstrap import bootstrap_local_environment
    from new_nfl.meta.adapter_slice_registry import sync_adapter_slices
    from new_nfl.settings import load_settings

    settings = load_settings()
    bootstrap_local_environment(settings)
    result = sync_adapter_slices(settings)
    print(f"REGISTRY_SLICE_COUNT={result.registry_slice_count}")
    print(f"UPSERTED_COUNT={result.upserted_count}")
    print(f"DELETED_ORPHAN_COUNT={result.deleted_orphan_count}")
    return 0


register_cli_plugin(
    CliPlugin(
        name="adapter-slice-sync",
        register_parser=_register_adapter_slice_sync,
        dispatch=_dispatch_adapter_slice_sync,
    )
)


# ---------------------------------------------------------------------------
# dedupe-review-resolve  (T2.7E-5)
# ---------------------------------------------------------------------------


def _register_dedupe_review_resolve(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "dedupe-review-resolve",
        help=(
            "Resolve a single meta.review_item via merge/reject/defer "
            "(T2.7E-5)"
        ),
    )
    parser.add_argument(
        "--review-id",
        required=True,
        help="review_item_id to resolve",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=("merge", "reject", "defer"),
        help="Resolution action",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional operator note stored on meta.review_item.note",
    )
    return parser


def _dispatch_dedupe_review_resolve(args: argparse.Namespace) -> int:
    from new_nfl.bootstrap import bootstrap_local_environment
    from new_nfl.dedupe.review import (
        InvalidReviewActionError,
        ReviewItemAlreadyResolvedError,
        ReviewItemNotFoundError,
        resolve_review_item,
    )
    from new_nfl.settings import load_settings

    settings = load_settings()
    bootstrap_local_environment(settings)
    try:
        result = resolve_review_item(
            settings,
            review_item_id=args.review_id,
            action=args.action,
            notes=args.notes,
        )
    except ReviewItemNotFoundError as exc:
        print(f"ERROR=not_found:{exc}")
        return 2
    except ReviewItemAlreadyResolvedError as exc:
        print(f"ERROR=already_resolved:{exc}")
        return 3
    except InvalidReviewActionError as exc:
        print(f"ERROR=invalid_action:{exc}")
        return 2

    print(f"REVIEW_ITEM_ID={result.review_item_id}")
    print(f"PREVIOUS_STATUS={result.previous_status}")
    print(f"NEW_STATUS={result.new_status}")
    print(f"RESOLUTION={result.resolution}")
    print(f"NOTES={result.notes or ''}")
    return 0


register_cli_plugin(
    CliPlugin(
        name="dedupe-review-resolve",
        register_parser=_register_dedupe_review_resolve,
        dispatch=_dispatch_dedupe_review_resolve,
    )
)


__all__: list[str] = []
