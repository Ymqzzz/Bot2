from __future__ import annotations

from typing import Iterable


def compute_brier_score(probs: Iterable[float], outcomes: Iterable[int]) -> float:
    pairs = list(zip(probs, outcomes))
    if not pairs:
        return 0.0
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def compute_reliability_curve(probs: list[float], outcomes: list[int], num_bins: int = 10) -> list[dict[str, float]]:
    if not probs:
        return []
    bins: list[list[tuple[float, int]]] = [[] for _ in range(num_bins)]
    for p, y in zip(probs, outcomes):
        idx = min(num_bins - 1, max(0, int(p * num_bins)))
        bins[idx].append((p, y))
    curve: list[dict[str, float]] = []
    for idx, bucket in enumerate(bins):
        if not bucket:
            continue
        avg_pred = sum(p for p, _ in bucket) / len(bucket)
        avg_obs = sum(y for _, y in bucket) / len(bucket)
        curve.append({"bin": idx, "avg_pred": avg_pred, "avg_obs": avg_obs, "count": float(len(bucket))})
    return curve


def compute_ece(probs: list[float], outcomes: list[int], num_bins: int = 10) -> float:
    curve = compute_reliability_curve(probs, outcomes, num_bins)
    n = max(len(probs), 1)
    return sum((point["count"] / n) * abs(point["avg_pred"] - point["avg_obs"]) for point in curve)


def compute_mce(probs: list[float], outcomes: list[int], num_bins: int = 10) -> float:
    curve = compute_reliability_curve(probs, outcomes, num_bins)
    if not curve:
        return 0.0
    return max(abs(point["avg_pred"] - point["avg_obs"]) for point in curve)
