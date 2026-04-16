"""Dedupe pipeline (T2.4B, ADR-0027).

Five-stage pipeline: ``normalize → block → score → cluster → review``.
v0_1 covers deterministic normalization, regel-basiertes Scoring und einen
Connected-Components-Cluster. Probabilistisches Matching ist als Scorer-
Interface offen für spätere ADRs.
"""
from __future__ import annotations

from new_nfl.dedupe.block import BlockedPair, build_blocks
from new_nfl.dedupe.cluster import Cluster, cluster_pairs
from new_nfl.dedupe.normalize import NormalizedPlayer, RawPlayerRecord, normalize_player_record
from new_nfl.dedupe.pipeline import DedupeRunResult, run_player_dedupe
from new_nfl.dedupe.review import open_review_items
from new_nfl.dedupe.score import RuleBasedPlayerScorer, ScoredPair, Scorer

__all__ = [
    "BlockedPair",
    "Cluster",
    "DedupeRunResult",
    "NormalizedPlayer",
    "RawPlayerRecord",
    "RuleBasedPlayerScorer",
    "ScoredPair",
    "Scorer",
    "build_blocks",
    "cluster_pairs",
    "normalize_player_record",
    "open_review_items",
    "run_player_dedupe",
]
