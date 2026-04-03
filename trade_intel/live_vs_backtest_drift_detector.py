from __future__ import annotations


def drift_score(live_metrics: dict[str, float], expected_metrics: dict[str, float]) -> float:
    if not live_metrics or not expected_metrics:
        return 0.0
    keys = set(live_metrics) & set(expected_metrics)
    if not keys:
        return 0.0
    diffs = []
    for k in keys:
        e = max(1e-9, abs(expected_metrics[k]))
        diffs.append(abs(live_metrics[k] - expected_metrics[k]) / e)
    score = sum(diffs) / len(diffs)
    return max(0.0, min(1.0, score))
