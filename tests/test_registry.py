"""Registry smoke tests (ADR-0033, T2.7P).

Verifies:

* every known ``mart_key`` is present in the mart-builder registry after
  importing :mod:`new_nfl.mart` — guards against a stream shipping a new
  mart module and forgetting the ``@register_mart_builder`` decorator
* duplicate registrations raise ``ValueError`` loudly instead of silently
  shadowing
* the CLI plugin registry surfaces the bundled ``registry-list`` plugin
  and round-trips a subcommand through ``build_parser`` + dispatch
"""
from __future__ import annotations

import argparse
import contextlib
import io

import pytest

from new_nfl.cli_plugins import (
    CliPlugin,
    get_cli_plugin,
    list_cli_plugins,
    register_cli_plugin,
)

EXPECTED_MART_KEYS: frozenset[str] = frozenset(
    {
        "freshness_overview_v1",
        "game_overview_v1",
        "player_overview_v1",
        "player_stats_career_v1",
        "player_stats_season_v1",
        "player_stats_weekly_v1",
        "provenance_v1",
        "roster_current_v1",
        "roster_history_v1",
        "run_evidence_v1",
        "schedule_field_dictionary_v1",
        "team_overview_v1",
        "team_stats_season_v1",
        "team_stats_weekly_v1",
    }
)


def test_mart_registry_lists_every_known_key() -> None:
    import new_nfl.mart  # noqa: F401  # triggers decorator registration
    from new_nfl.mart._registry import list_mart_keys

    registered = set(list_mart_keys())
    missing = EXPECTED_MART_KEYS - registered
    assert not missing, f"unregistered mart_keys: {sorted(missing)}"


def test_mart_registry_get_unknown_key_raises() -> None:
    import new_nfl.mart  # noqa: F401
    from new_nfl.mart._registry import get_mart_builder

    with pytest.raises(ValueError, match="unknown mart_key"):
        get_mart_builder("definitely_not_a_real_mart_key")


def test_mart_registry_duplicate_registration_raises() -> None:
    import new_nfl.mart  # noqa: F401
    from new_nfl.mart._registry import register_mart_builder

    with pytest.raises(ValueError, match="duplicate mart_key"):

        @register_mart_builder("team_overview_v1")
        def _impostor(settings):  # pragma: no cover - never called
            return None


def test_mart_registry_idempotent_self_reregistration() -> None:
    """Re-registering the exact same function object is a no-op.

    Protects against accidental double-imports (e.g., test harness
    reloading a module) without surfacing a false-positive duplicate.
    """
    import new_nfl.mart  # noqa: F401
    from new_nfl.mart._registry import (
        get_mart_builder,
        register_mart_builder,
    )

    existing = get_mart_builder("team_overview_v1")
    # Applying the decorator to the same function should succeed silently.
    returned = register_mart_builder("team_overview_v1")(existing)
    assert returned is existing


def test_cli_plugin_registry_lists_bundled_plugin() -> None:
    import new_nfl.plugins  # noqa: F401

    names = {plugin.name for plugin in list_cli_plugins()}
    assert "registry-list" in names


def test_cli_plugin_registry_duplicate_name_raises() -> None:
    def _noop_register(sub):  # pragma: no cover - never invoked
        return sub.add_parser("registry-list")

    def _noop_dispatch(args):  # pragma: no cover - never invoked
        return 0

    with pytest.raises(ValueError, match="duplicate cli_plugin"):
        register_cli_plugin(
            CliPlugin(
                name="registry-list",
                register_parser=_noop_register,
                dispatch=_noop_dispatch,
            )
        )


def test_cli_plugin_registry_idempotent_self_reregistration() -> None:
    existing = get_cli_plugin("registry-list")
    assert existing is not None
    returned = register_cli_plugin(existing)
    assert returned is existing


def test_cli_build_parser_attaches_plugin_subcommand() -> None:
    from new_nfl.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["registry-list", "--kind", "mart"])
    assert args.command == "registry-list"
    assert args.kind == "mart"


def test_cli_plugin_dispatch_prints_registered_mart_keys() -> None:
    plugin = get_cli_plugin("registry-list")
    assert plugin is not None
    args = argparse.Namespace(command="registry-list", kind="mart")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = plugin.dispatch(args)
    assert rc == 0
    output = buf.getvalue()
    assert "MART_KEY_COUNT=" in output
    for key in EXPECTED_MART_KEYS:
        assert key in output, f"{key} missing from dispatch output"
