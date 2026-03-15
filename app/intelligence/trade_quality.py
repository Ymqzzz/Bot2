from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.models import (
    CrossAssetContextState,
    EventRiskState,
    Evidence,
    InstrumentHealthState,
    MultiTimeframeBiasState,
    RegimeState,
    StrategyHealthState,
    StructureState,
    SweepState,
    TradeQualityState,
)


class TradeQualityEngine:
    def compute(
        self,
        *,
        timestamp,
        instrument: str,
        trace_id: str,
        regime: RegimeState,
        mtf: MultiTimeframeBiasState,
        structure: StructureState,
        sweep: SweepState,
        event_risk: EventRiskState,
        instrument_health: InstrumentHealthState,
        strategy_health: StrategyHealthState,
        cross_asset: CrossAssetContextState,
        candidate_strategy: str,
        execution_cost: float,
    ) -> TradeQualityState:
        strat_score = strategy_health.strategy_scores.get(candidate_strategy, 0.5)
        contrib = {
            "regime": regime.score_vector.get("trend", 0.0) - regime.score_vector.get("post_event_instability", 0.0),
            "alignment": mtf.alignment_score,
            "structure": structure.cleanliness_score,
            "sweep": sweep.reversal_probability if "reversal" in sweep.interpretation else sweep.continuation_probability,
            "event": 1.0 - event_risk.contamination_score,
            "instrument": instrument_health.health_score,
            "strategy": strat_score,
            "cross_asset": 1.0 - cross_asset.divergence_score,
            "execution": 1.0 - clamp(execution_cost),
        }
        weights = {"regime": 0.1, "alignment": 0.15, "structure": 0.15, "sweep": 0.1, "event": 0.1, "instrument": 0.15, "strategy": 0.15, "cross_asset": 0.05, "execution": 0.05}
        score = clamp(sum(contrib[k] * w for k, w in weights.items()))
        uncertainty = clamp(event_risk.contamination_score * 0.4 + mtf.conflict_score * 0.4 + (1.0 - structure.cleanliness_score) * 0.2)
        approval = clamp(score * (1.0 - 0.6 * uncertainty))
        label = "high" if score > 0.72 else "medium" if score > 0.48 else "low"
        size = clamp(0.4 + score - 0.5 * uncertainty, 0.2, 1.5)
        rationale = [Evidence(code, weights[code], value, "quality contribution") for code, value in contrib.items()]
        return TradeQualityState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - uncertainty),
            sources=["intelligence_engines"],
            rationale=rationale,
            quality_score=score,
            approval_confidence=approval,
            cleanliness_score=structure.cleanliness_score,
            uncertainty_score=uncertainty,
            quality_label=label,
            size_multiplier=size,
            contributions=contrib,
        )
