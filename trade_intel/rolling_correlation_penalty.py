from __future__ import annotations


def correlation_penalty(correlations: list[float], floor: float = 0.20, ceiling: float = 0.90) -> float:
    if not correlations:
        return 0.0
    avg = sum(abs(c) for c in correlations) / len(correlations)
    scaled = (avg - floor) / max(1e-8, ceiling - floor)
    return max(0.0, min(1.0, scaled))
