from __future__ import annotations


class SlippageEstimator:
    def estimate(self, volatility_score: float, imbalance_score: float, size_fraction: float) -> float:
        vol = max(0.0, min(1.0, volatility_score))
        imb = max(0.0, min(1.0, imbalance_score))
        size = max(0.0, min(1.0, size_fraction))
        return 0.01 + 0.04 * vol + 0.03 * imb + 0.05 * size
