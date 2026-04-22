"""Mart layer — read-only surface for UI / API / CLI browse (ADR-0029).

``core.*`` is the truth layer; ``mart.*`` is rebuildable from ``core.*`` and
is the only schema that UI / API / CLI-read paths are allowed to touch.
Mart tables are versioned with a ``_v<N>`` suffix so the read surface can
evolve without disturbing the canonical kernel.
"""
from new_nfl.mart.game_overview import (
    MART_GAME_OVERVIEW_V1,
    MartGameOverviewResult,
    build_game_overview_v1,
)
from new_nfl.mart.player_overview import (
    MART_PLAYER_OVERVIEW_V1,
    MartPlayerOverviewResult,
    build_player_overview_v1,
)
from new_nfl.mart.roster_current import (
    MART_ROSTER_CURRENT_V1,
    MartRosterCurrentResult,
    build_roster_current_v1,
)
from new_nfl.mart.roster_history import (
    MART_ROSTER_HISTORY_V1,
    MartRosterHistoryResult,
    build_roster_history_v1,
)
from new_nfl.mart.schedule_field_dictionary import (
    MART_SCHEDULE_FIELD_DICTIONARY_V1,
    MartBuildResult,
    build_schedule_field_dictionary_v1,
)
from new_nfl.mart.team_overview import (
    MART_TEAM_OVERVIEW_V1,
    MartTeamOverviewResult,
    build_team_overview_v1,
)
from new_nfl.mart.team_stats_season import (
    MART_TEAM_STATS_SEASON_V1,
    MartTeamStatsSeasonResult,
    build_team_stats_season_v1,
)
from new_nfl.mart.team_stats_weekly import (
    MART_TEAM_STATS_WEEKLY_V1,
    MartTeamStatsWeeklyResult,
    build_team_stats_weekly_v1,
)

__all__ = [
    "MART_GAME_OVERVIEW_V1",
    "MART_PLAYER_OVERVIEW_V1",
    "MART_ROSTER_CURRENT_V1",
    "MART_ROSTER_HISTORY_V1",
    "MART_SCHEDULE_FIELD_DICTIONARY_V1",
    "MART_TEAM_OVERVIEW_V1",
    "MART_TEAM_STATS_SEASON_V1",
    "MART_TEAM_STATS_WEEKLY_V1",
    "MartBuildResult",
    "MartGameOverviewResult",
    "MartPlayerOverviewResult",
    "MartRosterCurrentResult",
    "MartRosterHistoryResult",
    "MartTeamOverviewResult",
    "MartTeamStatsSeasonResult",
    "MartTeamStatsWeeklyResult",
    "build_game_overview_v1",
    "build_player_overview_v1",
    "build_roster_current_v1",
    "build_roster_history_v1",
    "build_schedule_field_dictionary_v1",
    "build_team_overview_v1",
    "build_team_stats_season_v1",
    "build_team_stats_weekly_v1",
]
