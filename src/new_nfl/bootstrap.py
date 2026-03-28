from __future__ import annotations

from pathlib import Path

from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings


def _ensure_dirs(settings: Settings) -> None:
    required_dirs = [
        settings.data_root,
        settings.data_root / "db",
        settings.raw_root,
        settings.raw_root / "planned",
        settings.raw_root / "landed",
        settings.stage_root,
        settings.exports_root,
        settings.temp_root,
        settings.ops_root,
        settings.ops_root / "quality_gates",
        settings.ops_root / "releases",
    ]
    for path in required_dirs:
        path.mkdir(parents=True, exist_ok=True)


def _ensure_db_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def bootstrap_local_environment(settings: Settings) -> Path:
    _ensure_dirs(settings)
    _ensure_db_parent(settings.db_path)
    ensure_metadata_surface(settings)
    return settings.db_path
