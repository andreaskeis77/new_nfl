"""Jinja-based renderer for the NEW NFL web UI (ADR-0030).

The renderer is a thin wrapper around a ``jinja2.Environment`` configured
with autoescaping for HTML/XML and a ``FileSystemLoader`` pointing at the
packaged ``templates/`` directory. Rendering is stateless; theme and asset
resolution are injected as template globals so views don't have to thread
them through every call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from new_nfl.web.assets import StaticAssetResolver, templates_dir

_SUPPORTED_THEMES = ("dark", "light")


@dataclass(frozen=True)
class NavItem:
    label: str
    href: str
    key: str


@dataclass(frozen=True)
class BreadcrumbItem:
    label: str
    href: str | None


DEFAULT_NAV: tuple[NavItem, ...] = (
    NavItem(label="Home", href="/", key="home"),
    NavItem(label="Seasons", href="/seasons", key="seasons"),
    NavItem(label="Teams", href="/teams", key="teams"),
    NavItem(label="Players", href="/players", key="players"),
    NavItem(label="Runs", href="/runs", key="runs"),
)


def _format_relative(value: Any, *, now: datetime | None = None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        value = parsed
    if not isinstance(value, datetime):
        return str(value)
    reference = now or datetime.now(tz=UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    delta = reference - value
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "gerade eben"
    if seconds < 60:
        return f"vor {seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"vor {minutes} min"
    hours = minutes // 60
    if hours < 48:
        return f"vor {hours} h"
    days = hours // 24
    return f"vor {days} Tagen"


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if isinstance(value, int):
        return f"{value:,}".replace(",", "\u00a0")
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", "\u00a0")
    return str(value)


@dataclass
class WebRenderer:
    environment: Environment
    assets: StaticAssetResolver = field(default_factory=StaticAssetResolver)
    default_theme: str = "dark"

    def render(
        self,
        template_name: str,
        *,
        context: dict[str, Any] | None = None,
        theme: str | None = None,
        active_nav: str = "",
        breadcrumb: tuple[BreadcrumbItem, ...] = (),
        page_title: str = "NEW NFL",
    ) -> str:
        ctx = dict(context or {})
        resolved_theme = theme if theme in _SUPPORTED_THEMES else self.default_theme
        ctx.setdefault("theme", resolved_theme)
        ctx.setdefault("active_nav", active_nav)
        ctx.setdefault("breadcrumb", breadcrumb)
        ctx.setdefault("page_title", page_title)
        ctx.setdefault("nav_items", DEFAULT_NAV)
        ctx.setdefault("assets", self.assets)
        template = self.environment.get_template(template_name)
        return template.render(**ctx)


def build_renderer(
    *,
    assets: StaticAssetResolver | None = None,
    default_theme: str = "dark",
) -> WebRenderer:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir())),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["relative_time"] = _format_relative
    env.filters["fmt_number"] = _format_number
    resolver = assets or StaticAssetResolver()
    return WebRenderer(environment=env, assets=resolver, default_theme=default_theme)


def render_home(
    *,
    renderer: WebRenderer | None = None,
    theme: str = "dark",
) -> str:
    r = renderer or build_renderer()
    context = {
        "hero": {
            "title": "NEW NFL",
            "subtitle": "Private Analytics Platform",
        },
        "stat_tiles": (
            {"label": "Teams", "value": 32, "delta": None, "delta_status": None},
            {"label": "Spieler", "value": 3072, "delta": "+12", "delta_status": "success"},
            {"label": "Saison", "value": 2024, "delta": None, "delta_status": None},
            {"label": "Offene Quarantäne", "value": 0, "delta": None, "delta_status": None},
        ),
        "freshness_sample": (
            {"domain": "Teams", "updated_at": None, "status": "success"},
            {"domain": "Games", "updated_at": None, "status": "success"},
            {"domain": "Players", "updated_at": None, "status": "warn"},
            {"domain": "Rosters", "updated_at": None, "status": "success"},
        ),
        "preview_rows": (
            {"season": 2024, "week": 1, "label": "KC @ BAL", "status": "final"},
            {"season": 2024, "week": 1, "label": "GB @ PHI", "status": "final"},
            {"season": 2024, "week": 1, "label": "PIT @ ATL", "status": "final"},
        ),
    }
    return r.render(
        "home.html",
        context=context,
        theme=theme,
        active_nav="home",
        breadcrumb=(BreadcrumbItem(label="Home", href=None),),
        page_title="NEW NFL — Home",
    )
