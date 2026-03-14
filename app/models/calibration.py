from __future__ import annotations


class ScoreCalibrator:
    """Lightweight monotonic score->probability mapper."""

    def __init__(self, floor: float = 0.05, cap: float = 0.95):
        self.floor = floor
        self.cap = cap

    def calibrate(self, raw_score: float, regime: str = "normal") -> float:
        s = max(0.0, min(1.0, float(raw_score)))
        if regime == "stress":
            s *= 0.80
        elif regime == "calm":
            s *= 1.05
        p = self.floor + (self.cap - self.floor) * s
        return max(self.floor, min(self.cap, p))
