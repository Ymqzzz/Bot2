from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.models import ConfidenceCalibrationState, Evidence, MarketIntelligenceSnapshot


class ConfidenceCalibrator:
    def compute(self, snapshot: MarketIntelligenceSnapshot, raw_confidence: float) -> ConfidenceCalibrationState:
        uncertainty = snapshot.uncertainty.uncertainty_score if snapshot.uncertainty else (snapshot.trade_quality.uncertainty_score if snapshot.trade_quality else 0.5)
        uncertainty_adj = snapshot.uncertainty.confidence_adjustment if snapshot.uncertainty else -0.35 * uncertainty
        analog_boost = (snapshot.analog.analog_confidence - 0.5) * 0.2 if snapshot.analog else 0.0
        calibrated = clamp(raw_confidence + uncertainty_adj + analog_boost)
        delta = calibrated - raw_confidence
        bucket = "boosted" if delta > 0.05 else "penalized" if delta < -0.05 else "neutral"
        return ConfidenceCalibrationState(
            timestamp=snapshot.timestamp,
            instrument=snapshot.instrument,
            trace_id=snapshot.trace_id,
            confidence=clamp(1.0 - uncertainty),
            sources=["uncertainty", "analog"],
            rationale=[
                Evidence("uncertainty_adjustment", 0.7, uncertainty_adj, "penalize conflicting evidence"),
                Evidence("analog_boost", 0.3, analog_boost, "confidence support from analog history"),
            ],
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            calibration_bucket=bucket,
            delta=delta,
        )
