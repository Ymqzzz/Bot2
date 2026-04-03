from __future__ import annotations


class EdgeHalfLifeEstimator:
    def estimate(self, *, decay_rate: float) -> float:
        if decay_rate <= 0:
            return 10_000.0
        return 0.693 / decay_rate
