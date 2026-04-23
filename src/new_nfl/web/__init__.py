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
from new_nfl.web.games_view import (
    GameRow,
    SeasonSummary,
    WeekSummary,
    list_games,
    list_seasons,
    list_weeks,
)
from new_nfl.web.renderer import (
    WebRenderer,
    build_renderer,
    render_home,
    render_home_from_settings,
    render_season_weeks_page,
    render_seasons_page,
    render_week_games_page,
)

__all__ = [
    "FreshnessRow",
    "GameRow",
    "HomeOverview",
    "SeasonSummary",
    "StaticAssetResolver",
    "WebRenderer",
    "WeekSummary",
    "build_home_overview",
    "build_renderer",
    "list_games",
    "list_seasons",
    "list_weeks",
    "load_freshness_rows",
    "render_home",
    "render_home_from_settings",
    "render_season_weeks_page",
    "render_seasons_page",
    "render_week_games_page",
    "static_asset_path",
]
