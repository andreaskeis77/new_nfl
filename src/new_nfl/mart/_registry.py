"""Mart-builder registry (ADR-0033).

Every ``mart.*`` read projection registers its builder function here via the
``@register_mart_builder("<mart_key>")`` decorator. The runner's
``_executor_mart_build`` dispatches on ``mart_key`` through this registry,
which eliminates the if/elif chain that was the primary merge-conflict
zone when multiple streams add new marts in parallel (T2.7 parallel phase).

The registry is populated at import time — ``new_nfl.mart`` must explicitly
import every mart module in ``__init__.py`` so the decorators fire before
any dispatch happens.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from new_nfl.settings import Settings

type MartBuilder = Callable[[Settings], Any]

_REGISTRY: dict[str, MartBuilder] = {}


def register_mart_builder(mart_key: str) -> Callable[[MartBuilder], MartBuilder]:
    """Decorator that binds a builder function to ``mart_key``.

    Raises ``ValueError`` on duplicate registration so typos and accidental
    double-imports surface immediately rather than silently shadowing.
    """

    def _decorator(fn: MartBuilder) -> MartBuilder:
        if mart_key in _REGISTRY:
            existing = _REGISTRY[mart_key]
            if existing is fn:
                return fn
            raise ValueError(
                f"duplicate mart_key={mart_key!r}: "
                f"already bound to {existing.__module__}.{existing.__name__}"
            )
        _REGISTRY[mart_key] = fn
        return fn

    return _decorator


def get_mart_builder(mart_key: str) -> MartBuilder:
    """Return the builder for ``mart_key`` or raise ``ValueError``."""
    if mart_key not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise ValueError(
            f"unknown mart_key={mart_key!r}; known keys: {known}"
        )
    return _REGISTRY[mart_key]


def list_mart_keys() -> list[str]:
    """Return the sorted list of registered mart_keys."""
    return sorted(_REGISTRY)


__all__ = [
    "MartBuilder",
    "get_mart_builder",
    "list_mart_keys",
    "register_mart_builder",
]
