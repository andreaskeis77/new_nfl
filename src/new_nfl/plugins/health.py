"""Plugin: ``new-nfl health-probe --kind <live|ready|freshness|deps>`` (T2.7A).

Thin CLI wrapper around :func:`new_nfl.observability.health.build_health_response`.
Prints the JSON envelope to stdout and returns a shell exit code that
reflects the probe status (``0`` ok, ``1`` warn, ``2`` fail).

Per the T2.7A scope the CLI is the primary surface — an optional HTTP
mirror may follow once a real web router lands (ADR-0033 deferral).
"""
from __future__ import annotations

import argparse
import json

from new_nfl.cli_plugins import CliPlugin, register_cli_plugin
from new_nfl.observability.health import (
    SUPPORTED_KINDS,
    build_health_response,
    exit_code_for,
)


def _register(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "health-probe",
        help="Run a JSON health probe (T2.7A)",
    )
    parser.add_argument(
        "--kind",
        default="live",
        choices=SUPPORTED_KINDS,
        help="Probe kind (default: live)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent JSON output for human reading (default: compact)",
    )
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    from new_nfl.settings import load_settings

    settings = load_settings()
    response = build_health_response(settings, args.kind)
    payload = response.to_dict()
    if getattr(args, "pretty", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return exit_code_for(response.status)


PLUGIN = register_cli_plugin(
    CliPlugin(
        name="health-probe",
        register_parser=_register,
        dispatch=_dispatch,
    )
)

__all__ = ["PLUGIN"]
