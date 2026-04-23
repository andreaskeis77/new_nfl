"""Schema-DESCRIBE-Cache-Tests (T2.7E-2a).

Deckt nur die Cache-Infrastruktur ab — die Integration in bestehende
Mart-Builder (T2.7E-2b) hat eigene Regressions-Tests über die jeweiligen
Mart-Test-Dateien.
"""
from __future__ import annotations

import time

import duckdb
import pytest

from new_nfl._db import connect
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.meta import schema_cache
from new_nfl.meta.schema_cache import (
    DEFAULT_TTL_SECONDS,
    cache_size,
    clear_cache,
    column_names,
    describe,
    invalidate_for,
)
from new_nfl.settings import load_settings


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_core_table(settings, table_name="core.player", *, columns=("player_id",)):
    con = connect(settings)
    try:
        schema = table_name.split(".")[0]
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cols_sql = ", ".join(f"{c} VARCHAR" for c in columns)
        con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_sql})")
    finally:
        con.close()


def test_describe_returns_column_rows(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, columns=("player_id", "display_name"))

    rows = describe(settings, "core.player")
    names = [str(row[0]).lower() for row in rows]
    assert names == ["player_id", "display_name"]


def test_column_names_helper(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, columns=("player_id", "Display_Name"))
    assert column_names(settings, "core.player") == {"player_id", "display_name"}


def test_describe_caches_result(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, columns=("player_id",))

    first = describe(settings, "core.player")
    assert cache_size() == 1

    # Drop the table behind the cache's back — the cached call must keep
    # returning the previously observed columns.
    con = connect(settings)
    try:
        con.execute("DROP TABLE core.player")
    finally:
        con.close()

    second = describe(settings, "core.player")
    assert second == first
    assert cache_size() == 1


def test_describe_respects_ttl_zero_does_not_cache(tmp_path, monkeypatch):
    """TTL=0 disables caching — every call re-DESCRIBES."""
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_SCHEMA_CACHE_TTL_SECONDS", "0")
    settings = _SettingsWithTTL(_bootstrap(tmp_path, monkeypatch), 0)
    _seed_core_table(settings.inner, columns=("player_id",))
    describe(settings, "core.player")
    assert cache_size() == 0


def test_describe_invalidate_for_settings(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, columns=("player_id",))
    describe(settings, "core.player")
    assert cache_size() == 1
    invalidate_for(settings)
    assert cache_size() == 0


def test_describe_invalidate_for_specific_table(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, table_name="core.player", columns=("player_id",))
    _seed_core_table(settings, table_name="core.team", columns=("team_id",))
    describe(settings, "core.player")
    describe(settings, "core.team")
    assert cache_size() == 2
    invalidate_for(settings, "core.player")
    assert cache_size() == 1


def test_describe_per_settings_isolation(tmp_path, monkeypatch):
    settings_a = _bootstrap(tmp_path / "a", monkeypatch)
    _seed_core_table(settings_a, columns=("player_id",))
    describe(settings_a, "core.player")

    # Second "settings" instance (same repo root is irrelevant; identity matters).
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path / "b"))
    settings_b = load_settings()
    bootstrap_local_environment(settings_b)
    _seed_core_table(settings_b, columns=("player_id", "extra"))
    describe(settings_b, "core.player")

    assert cache_size() == 2


def test_describe_uses_provided_connection(tmp_path, monkeypatch):
    """Passing a ``con`` avoids opening a second DuckDB connection."""
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, columns=("player_id",))

    con = connect(settings)
    try:
        rows = describe(settings, "core.player", con=con)
    finally:
        con.close()

    assert [str(row[0]).lower() for row in rows] == ["player_id"]


def test_describe_does_not_cache_errors(tmp_path, monkeypatch):
    settings = _bootstrap(tmp_path, monkeypatch)

    with pytest.raises(duckdb.Error):
        describe(settings, "core.does_not_exist")
    assert cache_size() == 0


def test_describe_ttl_expiry(tmp_path, monkeypatch):
    """After TTL elapses the next call re-DESCRIBES."""
    settings = _bootstrap(tmp_path, monkeypatch)
    _seed_core_table(settings, columns=("player_id",))
    wrapper = _SettingsWithTTL(settings, 1)

    describe(wrapper, "core.player")
    assert cache_size() == 1

    # Fast-forward time by monkeypatching time.monotonic used inside module.
    real_mono = time.monotonic
    try:
        monkeypatch.setattr(
            schema_cache.time, "monotonic", lambda: real_mono() + 3600
        )
        describe(wrapper, "core.player")
    finally:
        monkeypatch.setattr(schema_cache.time, "monotonic", real_mono)

    # Entry refreshed in place (cache_size stays 1 because the cutoff key
    # is identical — old expired row gets overwritten).
    assert cache_size() == 1


def test_default_ttl_seconds_constant():
    assert DEFAULT_TTL_SECONDS == 300


# ---------------------------------------------------------------------------
# _SettingsWithTTL shim
# ---------------------------------------------------------------------------


class _SettingsWithTTL:
    """Wrap a Settings instance with an overridden schema_cache_ttl_seconds.

    Settings is a frozen dataclass, so we can't mutate it; a proxy object
    with ``__getattr__`` lets the cache treat it like a normal Settings.
    The cache keys off ``id(settings)``, so two distinct proxies yield
    independent cache buckets — which is what we want here.
    """

    def __init__(self, inner, ttl: int):
        self.inner = inner
        self.schema_cache_ttl_seconds = ttl

    def __getattr__(self, name):
        return getattr(self.inner, name)
