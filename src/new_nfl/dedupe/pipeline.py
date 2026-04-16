"""End-to-end orchestrator (T2.4B, ADR-0027).

Bringt die fünf Stufen in einen einzigen, wiederholbaren Lauf zusammen und
schreibt Evidence in ``meta.dedupe_run``. Aktuell nur ``domain == "players"``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from new_nfl._db import connect, new_id
from new_nfl.dedupe.block import build_blocks
from new_nfl.dedupe.cluster import Cluster, cluster_pairs
from new_nfl.dedupe.normalize import RawPlayerRecord, normalize_player_record
from new_nfl.dedupe.review import insert_review_items
from new_nfl.dedupe.score import RuleBasedPlayerScorer, Scorer, score_pairs
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings

DEFAULT_LOWER_THRESHOLD = 0.50
DEFAULT_UPPER_THRESHOLD = 0.85


@dataclass(frozen=True)
class DedupeRunResult:
    dedupe_run_id: str
    domain: str
    source_ref: str
    scorer_kind: str
    lower_threshold: float
    upper_threshold: float
    input_record_count: int
    candidate_pair_count: int
    auto_merge_pair_count: int
    review_pair_count: int
    cluster_count: int
    run_status: str
    started_at: datetime
    ended_at: datetime
    clusters: tuple[Cluster, ...]


def run_player_dedupe(
    settings: Settings,
    *,
    records: list[RawPlayerRecord],
    source_ref: str = "demo",
    scorer: Scorer | None = None,
    lower_threshold: float = DEFAULT_LOWER_THRESHOLD,
    upper_threshold: float = DEFAULT_UPPER_THRESHOLD,
) -> DedupeRunResult:
    if upper_threshold < lower_threshold:
        raise ValueError("upper_threshold must be >= lower_threshold")
    ensure_metadata_surface(settings)
    scorer_impl: Scorer = scorer or RuleBasedPlayerScorer()
    started = datetime.now()
    dedupe_run_id = new_id()

    normalized = [normalize_player_record(r) for r in records]
    blocked = build_blocks(normalized)
    scored = score_pairs(blocked, scorer_impl)
    auto_merge = [p for p in scored if p.score >= upper_threshold]
    review = [p for p in scored if lower_threshold <= p.score < upper_threshold]
    clusters = cluster_pairs(normalized, scored, upper_threshold=upper_threshold)

    review_count = insert_review_items(
        settings,
        dedupe_run_id=dedupe_run_id,
        domain="players",
        pairs=review,
    )
    ended = datetime.now()
    con = connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.dedupe_run (
                dedupe_run_id, domain, source_ref, scorer_kind,
                lower_threshold, upper_threshold,
                input_record_count, candidate_pair_count,
                auto_merge_pair_count, review_pair_count,
                cluster_count, run_status, message, started_at, ended_at
            ) VALUES (?, 'players', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', NULL, ?, ?)
            """,
            [
                dedupe_run_id,
                source_ref,
                scorer_impl.kind,
                lower_threshold,
                upper_threshold,
                len(records),
                len(scored),
                len(auto_merge),
                review_count,
                len(clusters),
                started,
                ended,
            ],
        )
    finally:
        con.close()

    return DedupeRunResult(
        dedupe_run_id=dedupe_run_id,
        domain="players",
        source_ref=source_ref,
        scorer_kind=scorer_impl.kind,
        lower_threshold=lower_threshold,
        upper_threshold=upper_threshold,
        input_record_count=len(records),
        candidate_pair_count=len(scored),
        auto_merge_pair_count=len(auto_merge),
        review_pair_count=review_count,
        cluster_count=len(clusters),
        run_status="success",
        started_at=started,
        ended_at=ended,
        clusters=tuple(clusters),
    )


DEMO_PLAYER_RECORDS: tuple[RawPlayerRecord, ...] = (
    RawPlayerRecord(
        record_id="demo_p1",
        full_name="Patrick Mahomes II",
        position="QB",
        birth_year=1995,
        source_ref="demo:nflverse",
    ),
    RawPlayerRecord(
        record_id="demo_p2",
        full_name="Patrick Mahomes",
        position="QB",
        birth_year=1995,
        source_ref="demo:espn",
    ),
    RawPlayerRecord(
        record_id="demo_p3",
        full_name="Pat Mahomes",
        position="QB",
        birth_year=1965,
        source_ref="demo:legacy",
    ),
    RawPlayerRecord(
        record_id="demo_p4",
        full_name="Aaron Rodgers",
        position="QB",
        birth_year=1983,
        source_ref="demo:nflverse",
    ),
    RawPlayerRecord(
        record_id="demo_p5",
        full_name="A. Rodgers",
        position="QB",
        birth_year=1983,
        source_ref="demo:espn",
    ),
    RawPlayerRecord(
        record_id="demo_p6",
        full_name="Tom Brady",
        position="QB",
        birth_year=1977,
        source_ref="demo:nflverse",
    ),
)
