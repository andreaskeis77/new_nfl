"""Static asset resolver for the web layer.

Serves as the single source of truth for where static files live so that
v1.1+ can introduce content-hash cache-busters without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_WEB_PACKAGE_ROOT = Path(__file__).resolve().parent
_STATIC_ROOT = _WEB_PACKAGE_ROOT / "static"
_TEMPLATES_ROOT = _WEB_PACKAGE_ROOT / "templates"


def templates_dir() -> Path:
    return _TEMPLATES_ROOT


def static_dir() -> Path:
    return _STATIC_ROOT


def static_asset_path(relative: str) -> str:
    rel = relative.lstrip("/")
    return f"/static/{rel}"


@dataclass(frozen=True)
class StaticAssetResolver:
    base_path: str = "/static"

    def resolve(self, relative: str) -> str:
        rel = relative.lstrip("/")
        base = self.base_path.rstrip("/")
        return f"{base}/{rel}"

    def css(self, filename: str) -> str:
        return self.resolve(f"css/{filename}")

    def js(self, filename: str) -> str:
        return self.resolve(f"js/{filename}")

    def icon_sprite(self) -> str:
        return self.resolve("icons/lucide-sprite.svg")

    def font(self, filename: str) -> str:
        return self.resolve(f"fonts/{filename}")
