"""Stage 3 — pair scoring (T2.4B, ADR-0027 §3).

Phase-1 ist regelbasiert. Das ``Scorer``-Protokoll bleibt offen, damit ein
späteres probabilistisches Modell (Splink, Logistic Regression, …) ohne
Pipeline-Rewrite eingehängt werden kann.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from new_nfl.dedupe.block import BlockedPair
from new_nfl.dedupe.normalize import NormalizedPlayer


@dataclass(frozen=True)
class ScoredPair:
    block_key: str
    left: NormalizedPlayer
    right: NormalizedPlayer
    score: float


class Scorer(Protocol):
    kind: str

    def score(self, left: NormalizedPlayer, right: NormalizedPlayer) -> float:  # pragma: no cover - protocol
        ...


class RuleBasedPlayerScorer:
    """Deterministic, explainable scorer for Phase-1.

    Score-Stufen:
    - 1.00 — exakt identisches normalisiertes Tupel (Name + Pos + Year + Suffix)
    - 0.95 — normalisierter Name + Position + Birth-Year identisch
    - 0.80 — normalisierter Name + Birth-Year identisch (Position fehlt/abweichend)
    - 0.70 — normalisierter Name + Position identisch (kein Birth-Year-Konflikt)
    - 0.60 — Last-Name + First-Initial + Position + Birth-Year identisch (Initial-Match)
    - 0.50 — Last-Name + First-Initial identisch (Initial-only)
    - 0.00 — kein Match
    """

    kind = "rule_based_v1"

    def score(self, left: NormalizedPlayer, right: NormalizedPlayer) -> float:
        if left.record_id == right.record_id:
            return 0.0
        same_full = left.full_name_normalized == right.full_name_normalized
        same_position = (
            left.position_normalized is not None
            and left.position_normalized == right.position_normalized
        )
        birth_known_both = left.birth_year is not None and right.birth_year is not None
        same_birth = birth_known_both and left.birth_year == right.birth_year
        conflict_birth = birth_known_both and left.birth_year != right.birth_year

        if (
            same_full
            and same_position
            and same_birth
            and (left.suffix or "") == (right.suffix or "")
        ):
            return 1.0
        if same_full and same_position and same_birth:
            return 0.95
        if same_full and same_birth:
            return 0.80
        if same_full and same_position and not conflict_birth:
            return 0.70
        if (
            left.last_name
            and left.last_name == right.last_name
            and left.first_initial
            and left.first_initial == right.first_initial
            and same_position
            and same_birth
        ):
            return 0.60
        if (
            left.last_name
            and left.last_name == right.last_name
            and left.first_initial
            and left.first_initial == right.first_initial
            and not conflict_birth
        ):
            return 0.50
        return 0.0


def score_pairs(pairs: list[BlockedPair], scorer: Scorer) -> list[ScoredPair]:
    return [
        ScoredPair(block_key=p.block_key, left=p.left, right=p.right, score=scorer.score(p.left, p.right))
        for p in pairs
    ]
