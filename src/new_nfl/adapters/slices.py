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
    SliceSpec(
        adapter_id="nflverse_bulk",
        slice_key="games",
        label="NFL games (schedule + final scores)",
        remote_url=(
            "https://github.com/nflverse/nflverse-data/releases/download/"
            "schedules/games.csv"
        ),
        stage_target_object="nflverse_bulk_games",
        core_table="core.game",
        mart_key="game_overview_v1",
        tier_role="primary",
        notes=(
            "T2.5B primary games slice; Tier-A source of truth for game_id, "
            "schedule, final scores and venue metadata."
        ),
    ),
    SliceSpec(
        adapter_id="official_context_web",
        slice_key="games",
        label="Official context games cross-check",
        remote_url="",
        stage_target_object="official_context_web_games",
        core_table="",
        mart_key="",
        tier_role="cross_check",
        notes=(
            "T2.5B Tier-B cross-check feed for games. remote_url empty by design: "
            "operators pin a concrete URL per run via --remote-url or the SliceSpec "
            "is overridden in tests via remote_url_override. Triggers quarantine on "
            "score / venue drift against Tier-A."
        ),
    ),
    SliceSpec(
        adapter_id="nflverse_bulk",
        slice_key="players",
        label="NFL player master data",
        remote_url=(
            "https://github.com/nflverse/nflverse-data/releases/download/"
            "players/players.csv"
        ),
        stage_target_object="nflverse_bulk_players",
        core_table="core.player",
        mart_key="player_overview_v1",
        tier_role="primary",
        notes=(
            "T2.5C primary players slice; Tier-A source of truth for player_id, "
            "display_name, position, birth_date, draft metadata and current team. "
            "Feeds the first real dedupe application (ADR-0027) against core.player."
        ),
    ),
    SliceSpec(
        adapter_id="official_context_web",
        slice_key="players",
        label="Official context players cross-check",
        remote_url="",
        stage_target_object="official_context_web_players",
        core_table="",
        mart_key="",
        tier_role="cross_check",
        notes=(
            "T2.5C Tier-B cross-check feed for players. remote_url empty by design: "
            "operators pin a concrete URL per run via --remote-url or the SliceSpec "
            "is overridden in tests via remote_url_override. Triggers quarantine on "
            "display_name / position / jersey_number drift against Tier-A."
        ),
    ),
    SliceSpec(
        adapter_id="nflverse_bulk",
        slice_key="rosters",
        label="NFL weekly roster snapshots (bitemporal source, ADR-0032)",
        remote_url=(
            "https://github.com/nflverse/nflverse-data/releases/download/"
            "weekly_rosters/roster_weekly.csv"
        ),
        stage_target_object="nflverse_bulk_rosters",
        core_table="core.roster_membership",
        mart_key="roster_current_v1",
        tier_role="primary",
        notes=(
            "T2.5D primary rosters slice; first bitemporal domain (ADR-0032). "
            "Weekly snapshots collapsed into (player, team, season, from_week, "
            "to_week) intervals; open intervals have valid_to_week IS NULL. "
            "mart_key points at the current-roster projection; the full history "
            "mart roster_history_v1 is rebuilt alongside via the same promoter."
        ),
    ),
    SliceSpec(
        adapter_id="official_context_web",
        slice_key="rosters",
        label="Official context rosters cross-check",
        remote_url="",
        stage_target_object="official_context_web_rosters",
        core_table="",
        mart_key="",
        tier_role="cross_check",
        notes=(
            "T2.5D Tier-B cross-check feed for weekly rosters. remote_url empty "
            "by design: operators pin a concrete URL per run via --remote-url or "
            "the SliceSpec is overridden in tests via remote_url_override. "
            "Triggers quarantine on position / jersey_number / status drift "
            "against Tier-A at the (player, team, season, week) grain."
        ),
    ),
    SliceSpec(
        adapter_id="nflverse_bulk",
        slice_key="team_stats_weekly",
        label="NFL team statistics per (season, week, team)",
        remote_url=(
            "https://github.com/nflverse/nflverse-data/releases/download/"
            "stats_team/stats_team_week.csv"
        ),
        stage_target_object="nflverse_bulk_team_stats_weekly",
        core_table="core.team_stats_weekly",
        mart_key="team_stats_weekly_v1",
        tier_role="primary",
        notes=(
            "T2.5E primary team-stats slice. First aggregating domain: "
            "mart_key points at the weekly projection; the season aggregate "
            "mart team_stats_season_v1 is rebuilt alongside via the same "
            "promoter. Tier-A source of truth at the (season, week, team_id) grain."
        ),
    ),
    SliceSpec(
        adapter_id="official_context_web",
        slice_key="team_stats_weekly",
        label="Official context team-stats cross-check",
        remote_url="",
        stage_target_object="official_context_web_team_stats_weekly",
        core_table="",
        mart_key="",
        tier_role="cross_check",
        notes=(
            "T2.5E Tier-B cross-check feed for weekly team stats. remote_url "
            "empty by design; operators pin a URL per run via --remote-url or "
            "tests override via remote_url_override. Triggers quarantine on "
            "points_for / points_against / yards_for / turnovers drift against "
            "Tier-A at the (season, week, team_id) grain."
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
