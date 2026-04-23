"""Ontology-Auto-Aktivierung in bootstrap_local_environment (T2.7E-3)."""
from __future__ import annotations

import pytest

from new_nfl._db import connect
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings


def _copy_ontology_fixture(src_repo_root, dst_root):
    src = src_repo_root / "ontology" / "v0_1"
    dst = dst_root / "ontology" / "v0_1"
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.iterdir():
        if path.is_file() and path.suffix == ".toml":
            (dst / path.name).write_bytes(path.read_bytes())


def _make_settings(tmp_path, monkeypatch, *, with_ontology: bool):
    if with_ontology:
        repo_root = _find_repo_root()
        _copy_ontology_fixture(repo_root, tmp_path)
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_DATA_ROOT", str(tmp_path / "data"))
    return load_settings()


def _find_repo_root():
    from pathlib import Path

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "ontology" / "v0_1").is_dir():
            return parent
    raise RuntimeError("cannot locate repo root with ontology/v0_1")


def _count_active_versions(settings) -> int:
    con = connect(settings)
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM meta.ontology_version WHERE is_active = TRUE"
        ).fetchone()
    finally:
        con.close()
    return int(row[0])


def _active_version_id(settings) -> str | None:
    con = connect(settings)
    try:
        row = con.execute(
            "SELECT ontology_version_id FROM meta.ontology_version "
            "WHERE is_active = TRUE LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def test_bootstrap_auto_activates_default_ontology(tmp_path, monkeypatch):
    settings = _make_settings(tmp_path, monkeypatch, with_ontology=True)
    bootstrap_local_environment(settings)
    assert _count_active_versions(settings) == 1


def test_bootstrap_is_idempotent_on_repeat_calls(tmp_path, monkeypatch):
    settings = _make_settings(tmp_path, monkeypatch, with_ontology=True)
    bootstrap_local_environment(settings)
    bootstrap_local_environment(settings)
    bootstrap_local_environment(settings)
    assert _count_active_versions(settings) == 1


def test_bootstrap_skips_when_no_ontology_dir(tmp_path, monkeypatch):
    settings = _make_settings(tmp_path, monkeypatch, with_ontology=False)
    bootstrap_local_environment(settings)
    assert _count_active_versions(settings) == 0


def test_bootstrap_respects_skip_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD", "1")
    settings = _make_settings(tmp_path, monkeypatch, with_ontology=True)
    bootstrap_local_environment(settings)
    assert _count_active_versions(settings) == 0


def test_bootstrap_does_not_override_operator_loaded_version(tmp_path, monkeypatch):
    """If an operator already has an active version, auto-load is a no-op."""
    from new_nfl.ontology.loader import load_ontology_directory

    settings = _make_settings(tmp_path, monkeypatch, with_ontology=True)
    bootstrap_local_environment(settings)
    first_active_id = _active_version_id(settings)
    bootstrap_local_environment(settings)
    assert _active_version_id(settings) == first_active_id

    load_ontology_directory(
        settings, source_dir=tmp_path / "ontology" / "v0_1", activate=True
    )
    assert _active_version_id(settings) == first_active_id


def test_bootstrap_does_not_raise_on_broken_ontology(tmp_path, monkeypatch):
    """A corrupt TOML in the default dir must not break bootstrap."""
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_DATA_ROOT", str(tmp_path / "data"))
    broken_dir = tmp_path / "ontology" / "v0_1"
    broken_dir.mkdir(parents=True)
    (broken_dir / "term_broken.toml").write_text(
        "term_key = \n[this is not valid TOML", encoding="utf-8"
    )

    settings = load_settings()
    bootstrap_local_environment(settings)
    assert _count_active_versions(settings) == 0


@pytest.fixture(autouse=True)
def _clear_skip_env(monkeypatch):
    """Ensure the auto-load escape hatch is neutral unless a test sets it."""
    monkeypatch.delenv("NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD", raising=False)
