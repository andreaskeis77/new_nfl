"""Stage 5 — review queue (T2.4B, ADR-0027 §5).

Pairs mit ``lower_threshold <= score < upper_threshold`` landen als
``meta.review_item`` mit Status ``open``. Auto-Merge-Pairs (>= upper) und
No-Match-Pairs (< lower) werden hier nicht persistiert.
"""
from __future__ import annotations

import json
from typing import Any

from new_nfl._db import connect, new_id, row_to_dict
from new_nfl.dedupe.score import ScoredPair
from new_nfl.settings import Settings


def _payload(player: Any) -> str:
    return json.dumps(
        {
            "record_id": player.record_id,
            "full_name": player.full_name,
            "full_name_normalized": player.full_name_normalized,
            "position": player.position_normalized,
            "birth_year": player.birth_year,
            "source_ref": player.source_ref,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def insert_review_items(
    settings: Settings,
    *,
    dedupe_run_id: str,
    domain: str,
    pairs: list[ScoredPair],
) -> int:
    if not pairs:
        return 0
    con = connect(settings)
    try:
        for pair in pairs:
            con.execute(
                """
                INSERT INTO meta.review_item (
                    review_item_id, dedupe_run_id, domain,
                    left_record_id, right_record_id, score, block_key,
                    left_payload_json, right_payload_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """,
                [
                    new_id(),
                    dedupe_run_id,
                    domain,
                    pair.left.record_id,
                    pair.right.record_id,
                    pair.score,
                    pair.block_key,
                    _payload(pair.left),
                    _payload(pair.right),
                ],
            )
    finally:
        con.close()
    return len(pairs)


def open_review_items(
    settings: Settings,
    *,
    domain: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    con = connect(settings)
    try:
        if domain:
            return row_to_dict(
                con,
                """
                SELECT review_item_id, dedupe_run_id, domain, left_record_id, right_record_id,
                       score, block_key, status, created_at
                FROM meta.review_item
                WHERE status = 'open' AND domain = ?
                ORDER BY score DESC, created_at ASC
                LIMIT ?
                """,
                [domain, limit],
            )
        return row_to_dict(
            con,
            """
            SELECT review_item_id, dedupe_run_id, domain, left_record_id, right_record_id,
                   score, block_key, status, created_at
            FROM meta.review_item
            WHERE status = 'open'
            ORDER BY score DESC, created_at ASC
            LIMIT ?
            """,
            [limit],
        )
    finally:
        con.close()
