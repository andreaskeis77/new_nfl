"""T2.6A — UI Fundament (ADR-0030).

Verifies the Jinja-based renderer skeleton: base layout, component macros,
theme token behavior, and the AST-lint that the new web module stays
strictly on the read side (``mart.*`` only, ADR-0029). These tests do not
hit DuckDB — they exercise the pure rendering path only.
"""
from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from new_nfl.web import StaticAssetResolver, build_renderer, render_home
from new_nfl.web.assets import static_dir, templates_dir
from new_nfl.web.renderer import BreadcrumbItem, _format_relative


def test_static_asset_resolver_builds_url_with_default_base():
    resolver = StaticAssetResolver()
    assert resolver.css('app.css') == '/static/css/app.css'
    assert resolver.js('theme.js') == '/static/js/theme.js'
    assert resolver.icon_sprite() == '/static/icons/lucide-sprite.svg'


def test_static_asset_resolver_respects_custom_base():
    resolver = StaticAssetResolver(base_path='/ui/assets')
    assert resolver.css('app.css') == '/ui/assets/css/app.css'


def test_templates_and_static_directories_exist():
    assert templates_dir().is_dir(), 'web/templates/ must be packaged'
    assert static_dir().is_dir(), 'web/static/ must be packaged'
    assert (templates_dir() / 'base.html').is_file()
    assert (templates_dir() / 'home.html').is_file()
    assert (templates_dir() / '_components' / 'card.html').is_file()
    assert (templates_dir() / '_components' / 'stat_tile.html').is_file()
    assert (templates_dir() / '_components' / 'data_table.html').is_file()
    assert (templates_dir() / '_components' / 'navbar.html').is_file()
    assert (templates_dir() / '_components' / 'freshness_badge.html').is_file()
    assert (templates_dir() / '_components' / 'breadcrumb.html').is_file()
    assert (templates_dir() / '_components' / 'empty_state.html').is_file()
    assert (static_dir() / 'css' / 'app.css').is_file()
    assert (static_dir() / 'js' / 'theme.js').is_file()
    assert (static_dir() / 'icons' / 'lucide-sprite.svg').is_file()


def test_renderer_renders_home_dark_default():
    html = render_home()
    assert '<!DOCTYPE html>' in html
    assert 'data-theme="dark"' in html
    assert '<title>NEW NFL — Home</title>' in html
    assert 'href="/static/css/app.css"' in html
    assert 'nav-link-active' in html, 'active navbar item must be marked'
    assert 'NEW NFL' in html


def test_renderer_can_switch_to_light_theme():
    html = render_home(theme='light')
    assert 'data-theme="light"' in html


def test_unknown_theme_falls_back_to_default():
    renderer = build_renderer(default_theme='dark')
    html = renderer.render('home.html', context={
        'hero': {'title': 'NEW NFL', 'subtitle': 'Subtitle'},
        'stat_tiles': (),
        'freshness_sample': (),
        'preview_rows': (),
    }, theme='neon')
    assert 'data-theme="dark"' in html


def test_breadcrumb_renders_current_page_without_href():
    renderer = build_renderer()
    items = (
        BreadcrumbItem(label='Home', href='/'),
        BreadcrumbItem(label='Season 2024', href=None),
    )
    html = renderer.render(
        'home.html',
        context={
            'hero': {'title': 'NEW NFL', 'subtitle': 'Sub'},
            'stat_tiles': (),
            'freshness_sample': (),
            'preview_rows': (),
        },
        breadcrumb=items,
    )
    assert '<a href="/" class="hover:text-primary">Home</a>' in html
    assert 'aria-current="page" class="text-primary">Season 2024</span>' in html


def test_empty_state_rendered_when_no_preview_rows():
    renderer = build_renderer()
    html = renderer.render(
        'home.html',
        context={
            'hero': {'title': 'NEW NFL', 'subtitle': 'Sub'},
            'stat_tiles': (),
            'freshness_sample': (),
            'preview_rows': (),
        },
    )
    assert 'Noch keine Spiele' in html
    assert 'core-load' in html, 'empty-state hint must include a runnable CLI snippet'


def test_stat_tile_formats_integer_value_with_non_breaking_thousands():
    html = render_home()
    assert '3\u00a0072' in html, 'Spieler tile must use non-breaking thousands separator'


def test_freshness_badge_renders_relative_time_fallback_for_null():
    html = render_home()
    assert '—' in html, 'freshness badge must fall back to em-dash for NULL updated_at'


def test_relative_time_formats_recent_minutes():
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    value = now - timedelta(minutes=12)
    assert _format_relative(value, now=now) == 'vor 12 min'


def test_relative_time_formats_hours_and_days():
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    assert _format_relative(now - timedelta(hours=3), now=now) == 'vor 3 h'
    assert _format_relative(now - timedelta(days=5), now=now) == 'vor 5 Tagen'


def test_relative_time_handles_iso_string_input():
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    iso = (now - timedelta(minutes=5)).isoformat()
    assert _format_relative(iso, now=now) == 'vor 5 min'


def test_css_defines_dark_and_light_theme_tokens():
    css = (static_dir() / 'css' / 'app.css').read_text(encoding='utf-8')
    assert "html[data-theme='dark']" in css
    assert "html[data-theme='light']" in css
    assert '--bg-canvas' in css
    assert '--text-primary' in css
    assert '--accent' in css


def test_base_template_bootstraps_theme_before_stylesheet():
    base = (templates_dir() / 'base.html').read_text(encoding='utf-8')
    script_idx = base.find('localStorage.getItem')
    stylesheet_idx = base.find('rel="stylesheet"')
    assert 0 < script_idx < stylesheet_idx, (
        'theme bootstrap script must run before the stylesheet loads to avoid FOUC'
    )


def test_web_module_never_references_core_or_stg():
    repo_root = Path(__file__).resolve().parent.parent
    web_root = repo_root / 'src' / 'new_nfl' / 'web'
    forbidden = ('core.', 'stg.', 'raw/')
    offenders: list[tuple[str, int, str]] = []
    for py_path in web_root.rglob('*.py'):
        tree = ast.parse(py_path.read_text(encoding='utf-8'))
        doc_nodes: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body and isinstance(node.body[0], ast.Expr):
                    val = node.body[0].value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        doc_nodes.add(id(val))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in doc_nodes:
                    continue
                for token in forbidden:
                    if token in node.value:
                        offenders.append((str(py_path), node.lineno, node.value.strip()[:120]))
                        break
    assert not offenders, (
        'web modules must read only from mart.*; offenders:\n'
        + '\n'.join(f'  {p}:{n}: {v}' for p, n, v in offenders)
    )
