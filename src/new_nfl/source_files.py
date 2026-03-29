from __future__ import annotations

from dataclasses import dataclass

import duckdb

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.settings import Settings


@dataclass(frozen=True)
class SourceFilesResult:
    adapter_id: str
    total_row_count: int
    returned_row_count: int
    limit: int
    stage_dataset: str
    source_status: str
    rows: tuple[tuple[str, str, str, int, str, str], ...]


def list_source_files(
    settings: Settings,
    *,
    adapter_id: str,
    limit: int = 20,
) -> SourceFilesResult:
    if limit < 1:
        raise ValueError('limit must be >= 1')

    plan = build_adapter_plan(settings, adapter_id)

    con = duckdb.connect(str(settings.db_path))
    try:
        total_row_count = int(
            con.execute(
                'SELECT COUNT(*) FROM meta.source_files WHERE adapter_id = ?',
                [adapter_id],
            ).fetchone()[0]
        )
        rows = tuple(
            (
                str(source_file_id),
                str(created_at),
                str(local_path),
                int(file_size_bytes),
                str(sha256_hex),
                str(source_url),
            )
            for source_file_id, created_at, local_path, file_size_bytes, sha256_hex, source_url in con.execute(
                """
                SELECT
                    source_file_id,
                    CAST(created_at AS VARCHAR),
                    local_path,
                    COALESCE(file_size_bytes, 0),
                    COALESCE(sha256_hex, ''),
                    COALESCE(source_url, '')
                FROM meta.source_files
                WHERE adapter_id = ?
                ORDER BY created_at DESC, source_file_id DESC
                LIMIT ?
                """,
                [adapter_id, limit],
            ).fetchall()
        )
    finally:
        con.close()

    return SourceFilesResult(
        adapter_id=adapter_id,
        total_row_count=total_row_count,
        returned_row_count=len(rows),
        limit=limit,
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
        rows=rows,
    )
