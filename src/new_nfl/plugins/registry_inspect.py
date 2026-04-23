"""Plugin: ``new-nfl registry-list`` / ``registry-inspect`` (ADR-0033).

Proves the CLI plugin mechanism end-to-end and gives operators a way to
see which mart_keys are currently registered without opening the source.
Streams that add new marts will appear here automatically once their
module is imported via :mod:`new_nfl.mart.__init__`.
"""
from __future__ import annotations

import argparse

from new_nfl.cli_plugins import CliPlugin, register_cli_plugin


def _register(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "registry-list",
        help="List every registered mart_key (ADR-0033 registry)",
    )
    parser.add_argument(
        "--kind",
        default="mart",
        choices=("mart",),
        help="Registry kind (currently only 'mart' — extension point)",
    )
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    # Importing ``new_nfl.mart`` triggers every @register_mart_builder
    # decorator so the registry is fully populated before we list it.
    import new_nfl.mart  # noqa: F401
    from new_nfl.mart._registry import list_mart_keys

    if args.kind == "mart":
        keys = list_mart_keys()
        print(f"MART_KEY_COUNT={len(keys)}")
        for key in keys:
            print(key)
        return 0
    print(f"UNKNOWN_KIND={args.kind}")
    return 2


PLUGIN = register_cli_plugin(
    CliPlugin(
        name="registry-list",
        register_parser=_register,
        dispatch=_dispatch,
    )
)

__all__ = ["PLUGIN"]
