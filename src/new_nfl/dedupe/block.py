"""Stage 2 — blocking (T2.4B, ADR-0027 §2).

Reduziert das O(n²)-Pair-Universum auf nur Kandidaten, die denselben
Block-Key teilen. Block-Key für Player: ``last_name`` + Position +
Geburtsjahr (alle drei können fallweise leer sein, dann fällt der
entsprechende Anteil weg). Records ohne Last-Name werden nicht geblockt.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from new_nfl.dedupe.normalize import NormalizedPlayer


@dataclass(frozen=True)
class BlockedPair:
    block_key: str
    left: NormalizedPlayer
    right: NormalizedPlayer


def _player_block_key(player: NormalizedPlayer) -> str | None:
    if not player.last_name:
        return None
    parts = [player.last_name]
    if player.position_normalized:
        parts.append(player.position_normalized)
    if player.birth_year is not None:
        parts.append(str(player.birth_year))
    return "|".join(parts)


def build_blocks(players: list[NormalizedPlayer]) -> list[BlockedPair]:
    """Return all unordered candidate pairs sharing a block key.

    Pairs are deduplicated: ``(a, b)`` and ``(b, a)`` only appear once.
    """
    buckets: dict[str, list[NormalizedPlayer]] = {}
    for player in players:
        key = _player_block_key(player)
        if key is None:
            continue
        buckets.setdefault(key, []).append(player)
    pairs: list[BlockedPair] = []
    for key, bucket in buckets.items():
        if len(bucket) < 2:
            continue
        for left, right in combinations(bucket, 2):
            pairs.append(BlockedPair(block_key=key, left=left, right=right))
    return pairs
