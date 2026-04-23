"""CLI plugin namespace (ADR-0033).

Importing this package triggers registration of every bundled plugin via
their module-level ``register_cli_plugin`` calls. Parallel streams add
their CLI surface by dropping a new module under :mod:`new_nfl.plugins`
and importing it here.
"""
from new_nfl.plugins import (
    registry_inspect,  # noqa: F401  # registers plugin
    resilience,  # noqa: F401  # registers plugins (T2.7C/T2.7D)
)

__all__: list[str] = []
