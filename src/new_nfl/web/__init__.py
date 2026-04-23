"""Web layer — Jinja-based server-rendered UI (ADR-0030, ADR-0029).

Templates under ``templates/``, static assets under ``static/``. Only reads
from ``mart.*`` by AST-lint invariant; the UI never joins ``core.*`` or
``stg.*`` directly.
"""
from new_nfl.web.assets import StaticAssetResolver, static_asset_path
from new_nfl.web.renderer import WebRenderer, build_renderer, render_home

__all__ = [
    "StaticAssetResolver",
    "WebRenderer",
    "build_renderer",
    "render_home",
    "static_asset_path",
]
