from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ConfidenceCalibrator:
    staleness_half_life_sec: int = 600
    disagreement_penalty_weight: float = 0.35

    def calibrate(self, raw_confidence: float, staleness_sec: int, disagreement_score: float) -> float:
        confidence = max(0.0, min(1.0, float(raw_confidence)))
        staleness = max(0, int(staleness_sec))
        decay = 1.0 / (1.0 + staleness / max(1, self.staleness_half_life_sec))
        disagreement_penalty = max(0.0, min(0.95, disagreement_score * self.disagreement_penalty_weight))
        calibrated = confidence * decay * (1.0 - disagreement_penalty)
        return max(0.0, min(1.0, calibrated))

    def uncertainty(self, calibrated_confidence: float, volatility_score: float) -> float:
        vol = max(0.0, min(1.0, float(volatility_score)))
        uncertainty = (1.0 - calibrated_confidence) * 0.7 + vol * 0.3
        return max(0.0, min(1.0, uncertainty))
