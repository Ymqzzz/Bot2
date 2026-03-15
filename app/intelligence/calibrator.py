from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.models import ConfidenceCalibrationState, Evidence, MarketIntelligenceSnapshot


class ConfidenceCalibrator:
    def compute(self, snapshot: MarketIntelligenceSnapshot, raw_confidence: float) -> ConfidenceCalibrationState:
        uncertainty = snapshot.trade_quality.uncertainty_score if snapshot.trade_quality else 0.5
        analog_boost = (snapshot.analog.analog_confidence - 0.5) * 0.2 if snapshot.analog else 0.0
        penalty = uncertainty * 0.35
        calibrated = clamp(raw_confidence - penalty + analog_boost)
        delta = calibrated - raw_confidence
        bucket = "boosted" if delta > 0.05 else "penalized" if delta < -0.05 else "neutral"
        return ConfidenceCalibrationState(
            timestamp=snapshot.timestamp,
            instrument=snapshot.instrument,
            trace_id=snapshot.trace_id,
            confidence=clamp(1.0 - uncertainty),
            sources=["trade_quality", "analog"],
            rationale=[Evidence("uncertainty_penalty", 0.7, penalty, "penalize high-uncertainty states"), Evidence("analog_boost", 0.3, analog_boost, "confidence support from analog history")],
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            calibration_bucket=bucket,
            delta=delta,
        )
