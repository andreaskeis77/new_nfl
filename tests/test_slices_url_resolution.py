"""Tests for the URL-resolution helpers added in the T3.1 URL-drift fix.

``resolve_remote_url`` and ``default_nfl_season`` land in
``new_nfl.adapters.slices`` to support per-season slice URLs. The tests
below cover the calendar branches, the static-vs-template distinction
and the interaction with ``SLICE_REGISTRY``.
"""
from __future__ import annotations

from datetime import date

import pytest

from new_nfl.adapters.slices import (
    SliceSpec,
    default_nfl_season,
    get_slice,
    resolve_remote_url,
)


class TestDefaultNflSeason:
    def test_regular_season_window_returns_current_year(self) -> None:
        assert default_nfl_season(date(2025, 10, 1)) == 2025
        assert default_nfl_season(date(2025, 9, 1)) == 2025
        assert default_nfl_season(date(2025, 12, 31)) == 2025

    def test_january_february_still_prior_season(self) -> None:
        assert default_nfl_season(date(2026, 1, 15)) == 2025
        assert default_nfl_season(date(2026, 2, 28)) == 2025

    def test_offseason_uses_last_completed_season(self) -> None:
        assert default_nfl_season(date(2026, 4, 24)) == 2025
        assert default_nfl_season(date(2026, 7, 31)) == 2025
        assert default_nfl_season(date(2026, 8, 31)) == 2025

    def test_no_today_uses_system_clock(self) -> None:
        # Smoke only: must return an int within a sensible band.
        current = default_nfl_season()
        assert isinstance(current, int)
        assert 2020 <= current <= 2100


class TestResolveRemoteUrlStatic:
    def test_returns_static_url_unchanged(self) -> None:
        spec = SliceSpec(
            adapter_id="nflverse_bulk",
            slice_key="teams",
            label="test",
            remote_url="https://example.com/teams.csv",
            stage_target_object="x",
            core_table="core.team",
            mart_key="team_overview_v1",
            tier_role="primary",
            notes="",
        )
        assert resolve_remote_url(spec) == "https://example.com/teams.csv"

    def test_ignores_season_when_no_template(self) -> None:
        spec = SliceSpec(
            adapter_id="nflverse_bulk",
            slice_key="teams",
            label="test",
            remote_url="https://example.com/teams.csv",
            stage_target_object="x",
            core_table="core.team",
            mart_key="team_overview_v1",
            tier_role="primary",
            notes="",
        )
        assert resolve_remote_url(spec, season=2023) == "https://example.com/teams.csv"


class TestResolveRemoteUrlPerSeason:
    def _per_season_spec(self) -> SliceSpec:
        return SliceSpec(
            adapter_id="nflverse_bulk",
            slice_key="rosters",
            label="test",
            remote_url="",
            remote_url_template="https://example.com/roster_weekly_{season}.csv",
            stage_target_object="x",
            core_table="core.roster_membership",
            mart_key="roster_current_v1",
            tier_role="primary",
            notes="",
        )

    def test_explicit_season_rendered(self) -> None:
        spec = self._per_season_spec()
        assert (
            resolve_remote_url(spec, season=2023)
            == "https://example.com/roster_weekly_2023.csv"
        )

    def test_default_season_used_when_omitted(self) -> None:
        spec = self._per_season_spec()
        assert (
            resolve_remote_url(spec, today=date(2026, 4, 24))
            == "https://example.com/roster_weekly_2025.csv"
        )

    def test_explicit_season_overrides_today(self) -> None:
        spec = self._per_season_spec()
        assert (
            resolve_remote_url(spec, season=2022, today=date(2026, 4, 24))
            == "https://example.com/roster_weekly_2022.csv"
        )

    def test_is_per_season_property(self) -> None:
        spec = self._per_season_spec()
        assert spec.is_per_season is True


class TestRegistryIntegration:
    """Wire-up check: the actual SLICE_REGISTRY entries behave correctly."""

    def test_teams_slice_is_static_and_points_to_nflverse_data(self) -> None:
        spec = get_slice("nflverse_bulk", "teams")
        assert spec.is_per_season is False
        url = resolve_remote_url(spec)
        assert url.startswith("https://github.com/nflverse/nflverse-data/releases/download/teams/")

    def test_rosters_slice_is_per_season(self) -> None:
        spec = get_slice("nflverse_bulk", "rosters")
        assert spec.is_per_season is True
        url = resolve_remote_url(spec, season=2024)
        assert url.endswith("roster_weekly_2024.csv")

    def test_team_stats_weekly_is_per_season(self) -> None:
        spec = get_slice("nflverse_bulk", "team_stats_weekly")
        assert spec.is_per_season is True
        url = resolve_remote_url(spec, season=2024)
        assert url.endswith("stats_team_week_2024.csv")

    def test_player_stats_weekly_is_per_season(self) -> None:
        spec = get_slice("nflverse_bulk", "player_stats_weekly")
        assert spec.is_per_season is True
        url = resolve_remote_url(spec, season=2024)
        assert url.endswith("stats_player_week_2024.csv")

    @pytest.mark.parametrize(
        "slice_key",
        ["schedule_field_dictionary", "games", "players"],
    )
    def test_other_primary_slices_remain_static(self, slice_key: str) -> None:
        spec = get_slice("nflverse_bulk", slice_key)
        assert spec.is_per_season is False
        assert spec.remote_url.startswith("https://")
