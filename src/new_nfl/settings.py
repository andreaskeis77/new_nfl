from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_root() -> Path:
    override = os.environ.get("NEW_NFL_REPO_ROOT", "").strip()
    if not override:
        return _default_repo_root()

    candidate = Path(override)
    if candidate.is_absolute():
        return candidate

    return (_default_repo_root() / candidate).resolve()


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    env: str
    data_root: Path
    db_path: Path

    @property
    def docs_root(self) -> Path:
        return self.repo_root / "docs"

    @property
    def ops_root(self) -> Path:
        return self.docs_root / "_ops"

    @property
    def raw_root(self) -> Path:
        return self.data_root / "raw"

    @property
    def stage_root(self) -> Path:
        return self.data_root / "stage"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"

    @property
    def temp_root(self) -> Path:
        return self.data_root / "temp"

    @property
    def schema_cache_ttl_seconds(self) -> int:
        """TTL für den DESCRIBE-Cache in :mod:`new_nfl.meta.schema_cache` (T2.7E-2).

        ``NEW_NFL_SCHEMA_CACHE_TTL_SECONDS`` env-Override, Default 300s.
        Wert ``0`` deaktiviert das Caching vollständig (jeder Aufruf DESCRIBEt).
        """
        raw = os.environ.get("NEW_NFL_SCHEMA_CACHE_TTL_SECONDS", "").strip()
        if not raw:
            return 300
        try:
            return max(0, int(raw))
        except ValueError:
            return 300


def load_settings() -> Settings:
    repo_root = _resolve_repo_root()
    env = os.environ.get("NEW_NFL_ENV", "dev").strip() or "dev"

    data_root = Path(os.environ.get("NEW_NFL_DATA_ROOT", repo_root / "data"))
    if not data_root.is_absolute():
        data_root = (repo_root / data_root).resolve()

    db_path = Path(os.environ.get("NEW_NFL_DB_PATH", data_root / "db" / "new_nfl.duckdb"))
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve()

    return Settings(
        repo_root=repo_root,
        env=env,
        data_root=data_root,
        db_path=db_path,
    )
