from __future__ import annotations


def orthogonal_signal_score(cluster_count: int, engine_count: int, corr_penalty: float, overlap_penalty: float) -> float:
    if engine_count <= 0:
        return 0.0
    diversity = cluster_count / engine_count
    penalty = 0.6 * corr_penalty + 0.4 * overlap_penalty
    return max(0.0, min(1.0, diversity * (1.0 - penalty)))
