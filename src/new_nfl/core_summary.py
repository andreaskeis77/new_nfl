
from __future__ import annotations

from dataclasses import dataclass

import duckdb

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.settings import Settings


@dataclass(frozen=True)
class CoreSummaryResult:
    adapter_id: str
    source_schema: str
    source_object: str
    qualified_table: str
    total_row_count: int
    distinct_data_type_count: int
    stage_dataset: str
    source_status: str
    data_type_rows: tuple[tuple[str, int], ...]


def _target_table_for_adapter(adapter_id: str) -> tuple[str, str]:
    if adapter_id != 'nflverse_bulk':
        raise ValueError(
            'T2.0G only supports adapter_id=nflverse_bulk for the first summary core slice'
        )
    return ('core', 'schedule_field_dictionary')


def summarize_core_dictionary(
    settings: Settings,
    *,
    adapter_id: str,
) -> CoreSummaryResult:
    source_schema, source_object = _target_table_for_adapter(adapter_id)
    qualified_table = f'{source_schema}.{source_object}'
    plan = build_adapter_plan(settings, adapter_id)

    con = duckdb.connect(str(settings.db_path))
    try:
        total_row_count = int(
            con.execute(f'SELECT COUNT(*) FROM {qualified_table}').fetchone()[0]
        )
        data_type_rows = tuple(
            (
                str(row[0]),
                int(row[1]),
            )
            for row in con.execute(
                f"""
                SELECT data_type, COUNT(*) AS row_count
                FROM {qualified_table}
                GROUP BY data_type
                ORDER BY data_type
                """
            ).fetchall()
        )
    finally:
        con.close()

    return CoreSummaryResult(
        adapter_id=adapter_id,
        source_schema=source_schema,
        source_object=source_object,
        qualified_table=qualified_table,
        total_row_count=total_row_count,
        distinct_data_type_count=len(data_type_rows),
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
        data_type_rows=data_type_rows,
    )
