from pathlib import Path

from new_nfl.adapters import (
    build_adapter_plan,
    get_adapter_descriptor,
    list_adapter_descriptors,
)
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import seed_default_sources
from new_nfl.settings import load_settings


def test_adapter_catalog_contains_expected_source_ids() -> None:
    descriptors = list_adapter_descriptors()
    adapter_ids = {descriptor.adapter_id for descriptor in descriptors}

    assert adapter_ids == {
        "nflverse_bulk",
        "official_context_web",
        "public_stats_api",
        "reference_html_fallback",
    }


def test_get_adapter_descriptor_returns_one_row() -> None:
    descriptor = get_adapter_descriptor("nflverse_bulk")

    assert descriptor is not None
    assert descriptor.adapter_id == "nflverse_bulk"
    assert descriptor.dry_run_supported is True
    assert descriptor.transport == "file"


def test_build_adapter_plan_uses_registry_alignment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    plan = build_adapter_plan(settings, "public_stats_api")

    assert plan.registry_bound is True
    assert plan.source_status == "candidate"
    assert plan.stage_dataset == "stg.public_stats_api"
    assert Path(plan.raw_landing_prefix).as_posix().endswith(
        "data/raw/planned/public_stats_api"
    )
