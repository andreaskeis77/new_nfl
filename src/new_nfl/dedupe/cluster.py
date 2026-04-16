"""Stage 4 — clustering (T2.4B, ADR-0027 §4).

Connected-Components über alle Pairs mit ``score >= upper_threshold``.
Singletons (Records ohne Auto-Merge-Kante) zählen als eigene Cluster, damit
``cluster_count`` die wahre Anzahl distinkter Entitäten widerspiegelt.
"""
from __future__ import annotations

from dataclasses import dataclass

from new_nfl.dedupe.normalize import NormalizedPlayer
from new_nfl.dedupe.score import ScoredPair


@dataclass(frozen=True)
class Cluster:
    cluster_id: int
    record_ids: tuple[str, ...]


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self._parent: dict[str, str] = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self._parent[item]
        if parent == item:
            return item
        root = self.find(parent)
        self._parent[item] = root
        return root

    def union(self, left: str, right: str) -> None:
        root_l = self.find(left)
        root_r = self.find(right)
        if root_l != root_r:
            self._parent[root_l] = root_r


def cluster_pairs(
    players: list[NormalizedPlayer],
    scored: list[ScoredPair],
    *,
    upper_threshold: float,
) -> list[Cluster]:
    if not players:
        return []
    uf = _UnionFind([p.record_id for p in players])
    for pair in scored:
        if pair.score >= upper_threshold:
            uf.union(pair.left.record_id, pair.right.record_id)
    groups: dict[str, list[str]] = {}
    for player in players:
        root = uf.find(player.record_id)
        groups.setdefault(root, []).append(player.record_id)
    clusters: list[Cluster] = []
    for idx, ids in enumerate(sorted(groups.values(), key=lambda g: (len(g), g[0]), reverse=True)):
        clusters.append(Cluster(cluster_id=idx + 1, record_ids=tuple(ids)))
    return clusters
