from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import ThesisLeg, ThesisVector
from app.intelligence.adaptive.thesis_decay_monitor import ThesisDecayMonitor
from app.intelligence.adaptive.thesis_invalidation_rules import INVALIDATION_RULES
from app.intelligence.adaptive.thesis_quality_tracker import ThesisQualityTracker
from app.intelligence.adaptive.thesis_vector_schema import THESIS_COMPONENTS


@dataclass
class ThesisDecompositionEngine:
    quality_tracker: ThesisQualityTracker = ThesisQualityTracker()
    decay_monitor: ThesisDecayMonitor = ThesisDecayMonitor()

    def decompose(self, *, features: dict[str, float], context: dict) -> ThesisVector:
        component_inputs = {
            "directional_trend": clamp(float(features.get("directional_persistence", 0.5))),
            "liquidity_sweep": clamp(float(features.get("sweep_signal", 0.3))),
            "volatility_expansion": clamp(float(features.get("volatility_expansion", features.get("atr_percentile", 0.4)))),
            "orderflow_continuation": clamp(float(features.get("orderflow_continuation", 0.5))),
            "mean_reversion_snapback": clamp(float(features.get("reversion_readiness", 0.2))),
            "macro_alignment": clamp(float(context.get("macro_alignment_score", 0.5))),
            "behavioral_squeeze": clamp(float(features.get("squeeze_pressure", 0.3))),
        }

        total = sum(component_inputs.values()) or 1.0
        legs: list[ThesisLeg] = []
        fragility_accumulator = 0.0
        expectancy_accumulator = 0.0

        for thesis_id, raw_score in component_inputs.items():
            weight = raw_score / total
            decay = self.decay_monitor.estimate_decay(
                age_bars=float(context.get("setup_age_bars", 20.0)),
                regime_instability=float(context.get("regime_instability", features.get("volatility_noise", 0.3))),
            )
            fragility = clamp((1.0 - raw_score) * 0.6 + decay * 0.4)
            expectancy = self.quality_tracker.quality(
                win_rate=float(context.get("thesis_win_rate", 0.52)),
                expectancy=float(context.get("thesis_expectancy", 0.12)),
                fragility=fragility,
                decay=decay,
            )
            fragility_accumulator += fragility * weight
            expectancy_accumulator += expectancy * weight
            legs.append(
                ThesisLeg(
                    thesis_id=thesis_id,
                    weight=weight,
                    confidence=raw_score,
                    expected_contribution=expectancy,
                    invalidation_rule=INVALIDATION_RULES[thesis_id],
                )
            )

        dominant = max(legs, key=lambda leg: leg.weight).thesis_id if legs else "none"
        decay_score = self.decay_monitor.estimate_decay(
            age_bars=float(context.get("setup_age_bars", 20.0)),
            regime_instability=float(context.get("regime_instability", 0.25)),
        )
        return ThesisVector(
            legs=legs,
            dominant_thesis=dominant,
            fragility_score=clamp(fragility_accumulator),
            decay_score=decay_score,
            expectancy_score=clamp(expectancy_accumulator),
        )
