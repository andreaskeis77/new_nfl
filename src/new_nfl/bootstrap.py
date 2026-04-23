from __future__ import annotations

import os
from pathlib import Path

from new_nfl._db import connect
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings

_DEFAULT_ONTOLOGY_SUBDIR = Path("ontology") / "v0_1"


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


def _has_active_ontology_version(settings: Settings) -> bool:
    con = connect(settings)
    try:
        row = con.execute(
            "SELECT 1 FROM meta.ontology_version WHERE is_active = TRUE LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    return row is not None


def _auto_activate_default_ontology(settings: Settings) -> None:
    if os.environ.get("NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD", "").strip() == "1":
        return
    source_dir = settings.repo_root / _DEFAULT_ONTOLOGY_SUBDIR
    if not source_dir.is_dir():
        return
    if _has_active_ontology_version(settings):
        return
    try:
        from new_nfl.ontology.loader import load_ontology_directory

        load_ontology_directory(settings, source_dir=source_dir, activate=True)
    except Exception:
        return


def bootstrap_local_environment(settings: Settings) -> Path:
    _ensure_dirs(settings)
    _ensure_db_parent(settings.db_path)
    ensure_metadata_surface(settings)
    _auto_activate_default_ontology(settings)
    return settings.db_path
