"""Core-layer promotion logic (T2.5A+).

Core tables are the canonical, conflict-resolved, de-duplicated truth for a
domain. They are rebuilt idempotently from `stg.*` inputs and cross-checked
against Tier-B stage inputs via the quarantine domain (ADR-0028, ADR-0007).
"""
from new_nfl.core.games import CoreGameLoadResult, execute_core_game_load
from new_nfl.core.teams import CoreTeamLoadResult, execute_core_team_load

__all__ = [
    "CoreGameLoadResult",
    "CoreTeamLoadResult",
    "execute_core_game_load",
    "execute_core_team_load",
]
