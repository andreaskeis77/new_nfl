"""Slice registry for adapters (ADR-0031).

A *slice* is a distinct payload that flows through the `raw -> stg -> core ->
mart` pipeline. Historically each `adapter_id` had exactly one slice (the
T2.0A schedule-field dictionary); from T2.5A onwards one adapter can supply
multiple slices (teams, games, players, rosters, ...) and the same slice can
appear under multiple adapters (Tier-A primary + Tier-B cross-check).

This module is the single source of truth for slice dispatch. The
`stage_load`, `core_load`, `remote_fetch`, runner executors and CLI read from
`SLICE_REGISTRY` instead of hard-coding `if adapter_id == "X"` branches.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

TierRole = Literal["primary", "cross_check"]

DEFAULT_SLICE_KEY = "schedule_field_dictionary"


@dataclass(frozen=True)
class SliceSpec:
    adapter_id: str
    slice_key: str
    label: str
    remote_url: str
    stage_target_object: str
    core_table: str
    mart_key: str
    tier_role: TierRole
    notes: str

    @property
    def stage_qualified_table(self) -> str:
        return f"stg.{self.stage_target_object}"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_SLICE_SPECS: tuple[SliceSpec, ...] = (
    SliceSpec(
        adapter_id="nflverse_bulk",
        slice_key="schedule_field_dictionary",
        label="Schedule field dictionary (T2.0A legacy slice)",
        remote_url=(
            "https://raw.githubusercontent.com/nflverse/nflreadr/"
            "1f23027a27ec565f1272345a80a208b8f529f0fc/data-raw/dictionary_schedules.csv"
        ),
        stage_target_object="nflverse_bulk_schedule_dictionary",
        core_table="core.schedule_field_dictionary",
        mart_key="schedule_field_dictionary_v1",
        tier_role="primary",
        notes="First canonical slice delivered in T2.0A; keeps the default slice contract.",
    ),
    SliceSpec(
        adapter_id="nflverse_bulk",
        slice_key="teams",
        label="NFL franchises (current + historical)",
        remote_url=(
            "https://raw.githubusercontent.com/nflverse/nflreadr/"
            "1f23027a27ec565f1272345a80a208b8f529f0fc/data-raw/teams_colors_logos.csv"
        ),
        stage_target_object="nflverse_bulk_teams",
        core_table="core.team",
        mart_key="team_overview_v1",
        tier_role="primary",
        notes="T2.5A primary teams slice; Tier-A source of truth for abbreviation, name, division, colors.",
    ),
    SliceSpec(
        adapter_id="official_context_web",
        slice_key="teams",
        label="Official context teams cross-check",
        remote_url="",
        stage_target_object="official_context_web_teams",
        core_table="",
        mart_key="",
        tier_role="cross_check",
        notes=(
            "T2.5A Tier-B cross-check feed. Fixture-driven in v0.x; first real HTTP "
            "implementation in T2.5B+. Drives quarantine on Tier-A vs Tier-B disagreement."
        ),
    ),
)


SLICE_REGISTRY: dict[tuple[str, str], SliceSpec] = {
    (spec.adapter_id, spec.slice_key): spec for spec in _SLICE_SPECS
}


def list_slices() -> list[SliceSpec]:
    return list(_SLICE_SPECS)


def list_slices_for_adapter(adapter_id: str) -> list[SliceSpec]:
    return [spec for spec in _SLICE_SPECS if spec.adapter_id == adapter_id]


def get_slice(adapter_id: str, slice_key: str) -> SliceSpec:
    key = (adapter_id, slice_key)
    try:
        return SLICE_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"unknown slice adapter_id={adapter_id!r} slice_key={slice_key!r}"
        ) from exc


def slices_targeting_core_table(core_table: str) -> list[SliceSpec]:
    return [spec for spec in _SLICE_SPECS if spec.core_table == core_table]


def primary_slice_for_core_table(core_table: str) -> SliceSpec | None:
    for spec in _SLICE_SPECS:
        if spec.core_table == core_table and spec.tier_role == "primary":
            return spec
    return None


def cross_check_slices_for_primary(primary: SliceSpec) -> list[SliceSpec]:
    return [
        spec
        for spec in _SLICE_SPECS
        if spec.slice_key == primary.slice_key and spec.tier_role == "cross_check"
    ]


__all__ = [
    "DEFAULT_SLICE_KEY",
    "SLICE_REGISTRY",
    "SliceSpec",
    "TierRole",
    "cross_check_slices_for_primary",
    "get_slice",
    "list_slices",
    "list_slices_for_adapter",
    "primary_slice_for_core_table",
    "slices_targeting_core_table",
]
