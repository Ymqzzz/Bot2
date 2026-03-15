from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, StructureState, SweepState


class SweepEngine:
    def compute(self, data: EngineInput, structure: StructureState, liquidity: LiquidityState) -> SweepState:
        false_break = clamp(float(data.features.get("false_breakout_rate", 0.3)))
        spread = float(data.features.get("spread_percentile", 50.0))
        reversal_prob = clamp(0.55 * false_break + 0.2 * structure.messiness_penalty + 0.25 * (spread / 100.0))
        continuation_prob = clamp(1.0 - reversal_prob)
        detected = reversal_prob > 0.55 or continuation_prob > 0.7
        interpretation = "reversal" if reversal_prob >= continuation_prob else "continuation"
        sweep_type = "external_sweep_acceptance" if detected else "none"
        confidence = clamp(max(reversal_prob, continuation_prob))

        return SweepState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=confidence,
            sources=["features", "structure", "liquidity"],
            rationale=[Evidence("sweep", 1.0, confidence, "sweep probability from breakout and spread")],
            sweep_detected=detected,
            sweep_type=sweep_type,
            interpretation=interpretation,
            reversal_probability=reversal_prob,
            continuation_probability=continuation_prob,
            rejection_strength=reversal_prob,
            breached_pool_id=liquidity.most_significant_pool,
            breach_depth=clamp(float(data.features.get("breakout_follow_through", 0.5))),
            acceptance_strength=continuation_prob,
            follow_through_score=clamp(float(data.features.get("breakout_follow_through", 0.5))),
            post_sweep_state="active" if detected else "none",
            sweep_confidence=confidence,
        )
