from __future__ import annotations


def toxicity_penalty(taker_imbalance: float, short_horizon_drift: float) -> float:
    imbalance = abs(max(-1.0, min(1.0, taker_imbalance)))
    drift = abs(max(-1.0, min(1.0, short_horizon_drift)))
    return min(0.08, 0.04 * imbalance + 0.04 * drift)
