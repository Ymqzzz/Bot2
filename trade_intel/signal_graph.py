from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

from .feature_overlap_matrix import build_feature_overlap_matrix
from .orthogonal_signal_score import orthogonal_signal_score
from .rolling_correlation_penalty import correlation_penalty
from .signal_cluster_allocator import allocate_clusters


@dataclass(slots=True)
class SignalDependencyReport:
    disagreement_score: float
    redundancy_penalty: float
    orthogonal_score: float
    cluster_count: int
    reason_codes: list[str]


class SignalDependencyGraph:
    """Approximate redundancy and disagreement without heavy dependencies."""

    @staticmethod
    def _corr(xs: list[float], ys: list[float]) -> float:
        if len(xs) != len(ys) or len(xs) < 2:
            return 0.0
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        denx = sqrt(sum((x - mx) ** 2 for x in xs))
        deny = sqrt(sum((y - my) ** 2 for y in ys))
        if denx == 0.0 or deny == 0.0:
            return 0.0
        return max(-1.0, min(1.0, num / (denx * deny)))

    def analyze(self, candidate: dict[str, Any], market_context: dict[str, Any]) -> SignalDependencyReport:
        reasons: list[str] = []
        signals = candidate.get("engine_signals", {})
        if not isinstance(signals, dict) or not signals:
            return SignalDependencyReport(disagreement_score=0.2, redundancy_penalty=0.0, orthogonal_score=0.8, cluster_count=1, reason_codes=["SIGNAL_GRAPH_FALLBACK"])

        vectors: list[list[float]] = []
        for values in signals.values():
            if isinstance(values, list) and values:
                vectors.append([float(v) for v in values])
            else:
                vectors.append([float(values)])

        pair_corr: list[float] = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                n = min(len(vectors[i]), len(vectors[j]))
                pair_corr.append(abs(self._corr(vectors[i][:n], vectors[j][:n])))

        avg_corr = sum(pair_corr) / len(pair_corr) if pair_corr else 0.0
        corr_penalty = correlation_penalty(pair_corr)
        sign_votes = [1 if sum(v) >= 0 else -1 for v in vectors]
        disagreement = sign_votes.count(1) / len(sign_votes)
        disagreement = min(disagreement, 1 - disagreement) * 2
        feature_sets = {k: set(v) for k, v in candidate.get("engine_features", {}).items() if isinstance(v, list)}
        overlap_map = build_feature_overlap_matrix(feature_sets)
        overlap_penalty = sum(overlap_map.values()) / len(overlap_map) if overlap_map else 0.0
        clusters = allocate_clusters(overlap_map, threshold=0.60) if overlap_map else [{k} for k in signals]
        cluster_count = max(1, len(clusters))

        redundancy_penalty = max(0.0, min(0.9, avg_corr * 0.5 + overlap_penalty * 0.5))
        orthogonal = orthogonal_signal_score(cluster_count, len(vectors), corr_penalty, overlap_penalty)

        if redundancy_penalty > 0.5:
            reasons.append("SIGNAL_REDUNDANCY_HIGH")
        if disagreement > 0.5:
            reasons.append("DECISION_SIGNAL_CONFLICT")

        if market_context.get("regime_name") == "volatile":
            disagreement = min(1.0, disagreement + 0.1)

        return SignalDependencyReport(
            disagreement_score=disagreement,
            redundancy_penalty=redundancy_penalty,
            orthogonal_score=orthogonal,
            cluster_count=cluster_count,
            reason_codes=reasons,
        )
