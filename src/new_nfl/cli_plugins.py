"""CLI plugin registry (ADR-0033).

Extension point that lets streams add new ``new-nfl <command>`` subparsers
without editing ``build_parser()`` or ``main()`` in :mod:`new_nfl.cli`. That
keeps the monolithic parser file out of every stream's merge surface.

A plugin is a :class:`CliPlugin` triple of:

* ``name`` — the subcommand name (``new-nfl <name>``)
* ``register_parser`` — ``(subparsers) -> ArgumentParser`` that attaches the
  subparser and returns it (so ``--help`` renders the plugin's flags)
* ``dispatch`` — ``(argparse.Namespace) -> int`` executed when the user
  invokes ``<name>``; the return value becomes the CLI exit code

Plugins live under :mod:`new_nfl.plugins` and register themselves on
import. :mod:`new_nfl.cli` imports :mod:`new_nfl.plugins` so every plugin
module runs its registration before ``build_parser`` is called.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

RegisterParser = Callable[[argparse._SubParsersAction], argparse.ArgumentParser]
Dispatch = Callable[[argparse.Namespace], int]


@dataclass(frozen=True)
class CliPlugin:
    name: str
    register_parser: RegisterParser
    dispatch: Dispatch


_REGISTRY: dict[str, CliPlugin] = {}


def register_cli_plugin(plugin: CliPlugin) -> CliPlugin:
    """Register a plugin. Raises ``ValueError`` on duplicate ``name``."""
    if plugin.name in _REGISTRY:
        existing = _REGISTRY[plugin.name]
        if existing is plugin:
            return plugin
        raise ValueError(
            f"duplicate cli_plugin name={plugin.name!r}: "
            f"already bound to {existing.dispatch.__module__}."
            f"{existing.dispatch.__name__}"
        )
    _REGISTRY[plugin.name] = plugin
    return plugin


def get_cli_plugin(name: str) -> CliPlugin | None:
    """Return the plugin for ``name`` or ``None``."""
    return _REGISTRY.get(name)


def list_cli_plugins() -> list[CliPlugin]:
    """Return plugins sorted by name (stable for --help output)."""
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def attach_plugins_to_parser(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Invoke every registered plugin's ``register_parser`` on ``subparsers``.

    Called once from :func:`new_nfl.cli.build_parser` after the built-in
    subcommands are registered.
    """
    for plugin in list_cli_plugins():
        plugin.register_parser(subparsers)


__all__ = [
    "CliPlugin",
    "Dispatch",
    "RegisterParser",
    "attach_plugins_to_parser",
    "get_cli_plugin",
    "list_cli_plugins",
    "register_cli_plugin",
]
