from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import EventRiskState, Evidence, InstrumentHealthState, StructureState


class InstrumentHealthEngine:
    def compute(self, data: EngineInput, structure: StructureState, event_risk: EventRiskState) -> InstrumentHealthState:
        spread = clamp(float(data.features.get("spread_percentile", 0.2)))
        slippage = clamp(float(data.context.get("slippage_percentile", 0.2)))
        false_break = clamp(float(data.features.get("false_breakout_rate", 0.2)))
        volatility_noise = clamp(float(data.features.get("volatility_noise", 0.3)))

        score = clamp(
            1.0
            - 0.30 * spread
            - 0.20 * slippage
            - 0.20 * false_break
            - 0.15 * event_risk.contamination_score
            - 0.15 * (1.0 - structure.cleanliness_score)
            - 0.10 * volatility_noise
        )
        if event_risk.contamination_score > 0.65:
            label = "event_distorted"
        elif spread > 0.85:
            label = "spread_distorted"
        elif score > 0.72:
            label = "healthy"
        elif score > 0.45:
            label = "degraded"
        else:
            label = "unstable"
        tradable = score > 0.35 and label != "event_distorted"
        penalty = clamp(score, 0.25, 1.0)
        rationale = [
            Evidence("spread_percentile", 0.3, spread, "execution friction"),
            Evidence("event_contamination", 0.3, event_risk.contamination_score, "macro contamination"),
            Evidence("structure_cleanliness", 0.4, structure.cleanliness_score, "price action integrity"),
        ]
        return InstrumentHealthState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.5 + 0.5 * abs(score - 0.5)),
            sources=["features", "event", "structure"],
            rationale=rationale,
            health_score=score,
            health_label=label,
            tradable=tradable,
            penalty_multiplier=penalty,
        )
