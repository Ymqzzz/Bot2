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
    ) -> UncertaintyState:
        drivers = {
            "timeframe_conflict": mtf.conflict_score,
            "sweep_ambiguity": 1.0 - sweep.sweep_confidence if sweep.sweep_detected else 0.55,
            "structure_messiness": structure.messiness_penalty,
            "event_contamination": event_risk.contamination_score,
            "instrument_degradation": 1.0 - instrument_health.health_score,
            "strategy_sample_uncertainty": 1.0 - max(strategy_health.sample_quality_scores.values(), default=0.0),
            "analog_sparsity": 1.0 - analog_confidence,
            "cross_asset_conflict": cross_asset.divergence_score,
        }
        weights = {
            "timeframe_conflict": 0.16,
            "sweep_ambiguity": 0.14,
            "structure_messiness": 0.14,
            "event_contamination": 0.16,
            "instrument_degradation": 0.10,
            "strategy_sample_uncertainty": 0.12,
            "analog_sparsity": 0.10,
            "cross_asset_conflict": 0.08,
        }
        score = clamp(sum(drivers[k] * w for k, w in weights.items()))
        label = "extreme" if score > 0.8 else "high" if score > 0.62 else "moderate" if score > 0.4 else "low"
        confidence_adjustment = clamp(-0.45 * score, -0.45, 0.0)
        size_penalty = clamp(1.0 - 0.65 * score, 0.25, 1.0)
        rank_penalty = clamp(0.55 * score)
        rationale = [Evidence(code, weights[code], value, "uncertainty driver") for code, value in drivers.items()]
        return UncertaintyState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - score),
            sources=["mtf", "structure", "sweep", "event", "instrument", "strategy", "cross_asset", "analog"],
            rationale=rationale,
            uncertainty_score=score,
            uncertainty_label=label,
            uncertainty_drivers=drivers,
            confidence_adjustment=confidence_adjustment,
            size_penalty_multiplier=size_penalty,
            ranking_penalty=rank_penalty,
            block_if_extreme_flag=score > 0.9,
        )
