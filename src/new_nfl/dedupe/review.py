"""Stage 5 — review queue (T2.4B, ADR-0027 §5).

Pairs mit ``lower_threshold <= score < upper_threshold`` landen als
``meta.review_item`` mit Status ``open``. Auto-Merge-Pairs (>= upper) und
No-Match-Pairs (< lower) werden hier nicht persistiert.

T2.7E-5 erweitert die Review-Surface um :func:`resolve_review_item`
(Operator-Aktionen ``merge`` / ``reject`` / ``defer``) — Einstieg für
die CLI ``new-nfl dedupe-review-resolve`` und zukünftige Web-Reviewer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from new_nfl._db import connect, new_id, row_to_dict
from new_nfl.dedupe.score import ScoredPair
from new_nfl.settings import Settings

_ACTION_MERGE = "merge"
_ACTION_REJECT = "reject"
_ACTION_DEFER = "defer"
RESOLVE_ACTIONS: tuple[str, ...] = (_ACTION_MERGE, _ACTION_REJECT, _ACTION_DEFER)


class ReviewItemNotFoundError(LookupError):
    """Raised when :func:`resolve_review_item` cannot find the given review_item_id."""


class ReviewItemAlreadyResolvedError(RuntimeError):
    """Raised when the review item is already in a terminal/non-open state."""


class InvalidReviewActionError(ValueError):
    """Raised when the requested action is not one of merge/reject/defer."""


@dataclass(frozen=True)
class ReviewResolution:
    review_item_id: str
    previous_status: str
    new_status: str
    resolution: str
    notes: str | None


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


def resolve_review_item(
    settings: Settings,
    *,
    review_item_id: str,
    action: str,
    notes: str | None = None,
) -> ReviewResolution:
    """Apply operator-level resolution to a single ``meta.review_item``.

    * ``merge`` / ``reject`` → ``status='resolved'``, ``resolution=<action>``
      (terminal — the item drops out of the open queue for good).
    * ``defer`` → ``status='deferred'``, ``resolution='defer'`` (explicitly
      shelved; a later ``defer`` or resolve can still override it).

    ``notes`` are written into ``meta.review_item.note``. The function is
    idempotent for ``defer`` (re-deferring is a no-op re-stamp) but refuses
    to overwrite a terminal resolution — use a new CLI invocation against a
    fresh review item if the domain case reopens.
    """
    normalized = action.strip().lower()
    if normalized not in RESOLVE_ACTIONS:
        raise InvalidReviewActionError(
            f"action must be one of {RESOLVE_ACTIONS}, got {action!r}"
        )

    con = connect(settings)
    try:
        row = con.execute(
            """
            SELECT status, resolution FROM meta.review_item
            WHERE review_item_id = ?
            """,
            [review_item_id],
        ).fetchone()
        if row is None:
            raise ReviewItemNotFoundError(
                f"review_item_id not found: {review_item_id!r}"
            )
        previous_status = str(row[0])
        if previous_status == "resolved":
            raise ReviewItemAlreadyResolvedError(
                f"review_item {review_item_id!r} is already resolved "
                f"(resolution={row[1]!r}); refusing to overwrite"
            )

        if normalized == _ACTION_DEFER:
            new_status = "deferred"
            resolution = _ACTION_DEFER
            con.execute(
                """
                UPDATE meta.review_item
                SET status = ?, resolution = ?, note = ?,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE review_item_id = ?
                """,
                [new_status, resolution, notes, review_item_id],
            )
        else:
            new_status = "resolved"
            resolution = normalized
            con.execute(
                """
                UPDATE meta.review_item
                SET status = ?, resolution = ?, note = ?,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE review_item_id = ?
                """,
                [new_status, resolution, notes, review_item_id],
            )
    finally:
        con.close()

    return ReviewResolution(
        review_item_id=review_item_id,
        previous_status=previous_status,
        new_status=new_status,
        resolution=resolution,
        notes=notes,
    )


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
