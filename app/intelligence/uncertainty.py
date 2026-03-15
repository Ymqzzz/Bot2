from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.models import (
    CrossAssetContextState,
    EventRiskState,
    Evidence,
    InstrumentHealthState,
    MultiTimeframeBiasState,
    StrategyHealthState,
    StructureState,
    SweepState,
    UncertaintyState,
)


class UncertaintyEngine:
    @staticmethod
    def _sample_quality(sample_quality_scores):
        if isinstance(sample_quality_scores, dict):
            return max(sample_quality_scores.values(), default=0.0)
        try:
            return float(sample_quality_scores)
        except (TypeError, ValueError):
            return 0.0

    def compute(
        self,
        *,
        timestamp,
        instrument: str,
        trace_id: str,
        mtf: MultiTimeframeBiasState,
        structure: StructureState,
        sweep: SweepState,
        event_risk: EventRiskState,
        instrument_health: InstrumentHealthState,
        strategy_health: StrategyHealthState,
        cross_asset: CrossAssetContextState,
        analog_confidence: float,
        spread_percentile: float = 50.0,
    ) -> UncertaintyState:
        drivers = {
            "mtf_conflict": mtf.conflict_score,
            "sweep_ambiguity": 1.0 - sweep.sweep_confidence,
            "structure_messiness": structure.messiness_penalty,
            "event_contamination": event_risk.contamination_score,
            "instrument_degradation": 1.0 - instrument_health.health_score,
            "strategy_sample_uncertainty": 1.0 - self._sample_quality(strategy_health.sample_quality_scores),
            "analog_sparsity": 1.0 - analog_confidence,
            "cross_asset_conflict": cross_asset.divergence_score,
            "spread_stress": clamp(spread_percentile / 100.0),
        }
        weights = {
            "mtf_conflict": 0.2,
            "sweep_ambiguity": 0.14,
            "structure_messiness": 0.14,
            "event_contamination": 0.14,
            "instrument_degradation": 0.1,
            "strategy_sample_uncertainty": 0.1,
            "analog_sparsity": 0.1,
            "cross_asset_conflict": 0.05,
            "spread_stress": 0.03,
        }
        score = clamp(sum(drivers[k] * weights[k] for k in weights))
        label = "extreme" if score > 0.78 else "high" if score > 0.62 else "moderate" if score > 0.4 else "low"
        return UncertaintyState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - score),
            sources=["intelligence_engines"],
            rationale=[Evidence(code, weights[code], value, "uncertainty driver") for code, value in drivers.items()],
            uncertainty_score=score,
            uncertainty_label=label,
            uncertainty_drivers=drivers,
            confidence_adjustment=-0.35 * score,
            size_penalty_multiplier=clamp(1.0 - 0.6 * score, 0.25, 1.0),
            ranking_penalty=clamp(0.7 * score),
            block_if_extreme_flag=label == "extreme",
        )
