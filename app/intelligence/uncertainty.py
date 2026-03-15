from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.models import (
    CrossAssetContextState,
    EventRiskState,
    Evidence,
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
        strategy_health: StrategyHealthState,
        cross_asset: CrossAssetContextState,
        analog_confidence: float,
        spread_percentile: float,
    ) -> UncertaintyState:
        drivers = {
            "mtf_conflict": mtf.conflict_score,
            "sweep_ambiguity": 1.0 - sweep.sweep_confidence,
            "structure_messiness": structure.messiness_penalty,
            "event_contamination": event_risk.contamination_score,
            "strategy_sample_uncertainty": 1.0 - strategy_health.confidence,
            "analog_sparsity": 1.0 - analog_confidence,
            "cross_asset_conflict": cross_asset.divergence_score,
            "spread_stress": clamp(spread_percentile / 100.0),
        }
        weights = {
            "mtf_conflict": 0.22,
            "sweep_ambiguity": 0.14,
            "structure_messiness": 0.15,
            "event_contamination": 0.14,
            "strategy_sample_uncertainty": 0.1,
            "analog_sparsity": 0.1,
            "cross_asset_conflict": 0.08,
            "spread_stress": 0.07,
        }
        score = clamp(sum(drivers[k] * weights[k] for k in weights))
        label = "extreme" if score > 0.78 else "high" if score > 0.62 else "moderate" if score > 0.4 else "low"
        confidence_adj = -0.35 * score
        size_penalty = clamp(1.0 - 0.6 * score, 0.25, 1.0)
        rank_penalty = clamp(0.7 * score)
        return UncertaintyState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - score),
            sources=["mtf", "structure", "sweep", "event", "strategy_health", "analog", "cross_asset"],
            rationale=[Evidence(code, weights[code], value, "uncertainty driver") for code, value in drivers.items()],
            uncertainty_score=score,
            uncertainty_label=label,
            uncertainty_drivers=drivers,
            confidence_adjustment=confidence_adj,
            size_penalty_multiplier=size_penalty,
            ranking_penalty=rank_penalty,
            block_if_extreme_flag=label == "extreme",
        )
