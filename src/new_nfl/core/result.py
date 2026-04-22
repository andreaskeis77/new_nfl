"""Common protocol for core-load results (T2.5C, methodology carry-over from T2.5B).

Every `execute_core_*_load` promoter (teams, games, players, ...) returns a
frozen dataclass with slice-specific extras. The CLI and runner need a stable
common surface for dispatch and printing — we capture that here as a
`typing.Protocol` rather than a shared base class, so each concrete result
remains a plain `@dataclass(frozen=True)` without inheritance bookkeeping.

The eleven attributes below are the minimum shape any core-load result must
expose. Slice-specific fields (`distinct_team_count`, `conflict_count`,
`opened_quarantine_case_ids`, etc.) stay on the concrete dataclass and remain
reachable via ``isinstance`` branches where the CLI needs to surface them.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CoreLoadResultLike(Protocol):
    run_mode: str
    run_status: str
    pipeline_name: str
    ingest_run_id: str
    qualified_table: str
    source_row_count: int
    row_count: int
    invalid_row_count: int
    load_event_id: str
    mart_qualified_table: str
    mart_row_count: int


def print_common_core_load_lines(result: CoreLoadResultLike) -> None:
    """Pipe-aligned CLI output shared across all core-load result shapes."""
    print(f'PIPELINE_NAME={result.pipeline_name}')
    print(f'RUN_MODE={result.run_mode}')
    print(f'RUN_STATUS={result.run_status}')
    print(f'INGEST_RUN_ID={result.ingest_run_id}')
    print(f'QUALIFIED_TABLE={result.qualified_table}')
    print(f'SOURCE_ROW_COUNT={result.source_row_count}')
    print(f'ROW_COUNT={result.row_count}')
    print(f'INVALID_ROW_COUNT={result.invalid_row_count}')
    print(f'LOAD_EVENT_ID={result.load_event_id}')
    print(f'MART_QUALIFIED_TABLE={result.mart_qualified_table}')
    print(f'MART_ROW_COUNT={result.mart_row_count}')


__all__ = [
    "CoreLoadResultLike",
    "print_common_core_load_lines",
]
