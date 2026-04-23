"""Web layer — Jinja-based server-rendered UI (ADR-0030, ADR-0029).

Templates under ``templates/``, static assets under ``static/``. Only reads
from ``mart.*`` by AST-lint invariant; the UI never joins ``core.*`` or
``stg.*`` directly.
"""
from new_nfl.web.assets import StaticAssetResolver, static_asset_path
from new_nfl.web.freshness import (
    FreshnessRow,
    HomeOverview,
    build_home_overview,
    load_freshness_rows,
)
from new_nfl.web.renderer import (
    WebRenderer,
    build_renderer,
    render_home,
    render_home_from_settings,
)

__all__ = [
    "FreshnessRow",
    "HomeOverview",
    "StaticAssetResolver",
    "WebRenderer",
    "build_home_overview",
    "build_renderer",
    "load_freshness_rows",
    "render_home",
    "render_home_from_settings",
    "static_asset_path",
]
