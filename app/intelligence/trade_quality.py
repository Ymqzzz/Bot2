from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.models import (
    CrossAssetContextState,
    EventRiskState,
    Evidence,
    InstrumentHealthState,
    LiquidityState,
    MultiTimeframeBiasState,
    RegimeState,
    StrategyHealthState,
    StructureState,
    SweepState,
    TradeQualityState,
    UncertaintyState,
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
        liquidity: LiquidityState,
        sweep: SweepState,
        event_risk: EventRiskState,
        instrument_health: InstrumentHealthState,
        strategy_health: StrategyHealthState,
        cross_asset: CrossAssetContextState,
        candidate_strategy: str,
        execution_cost: float,
        uncertainty: UncertaintyState | None = None,
    ) -> TradeQualityState:
        strat_score = strategy_health.strategy_scores.get(candidate_strategy, 0.5)
        strategy_penalty = strategy_health.rank_penalties.get(candidate_strategy, 0.0)
        alignment = clamp(0.6 * mtf.alignment_score + 0.4 * (1.0 - mtf.conflict_score))
        context_penalty = clamp(
            0.35 * event_risk.contamination_score
            + 0.20 * mtf.conflict_score
            + 0.20 * structure.messiness_penalty
            + 0.15 * cross_asset.divergence_score
            + 0.10 * strategy_penalty
        )
        execution_burden = clamp(execution_cost)
        contrib = {
            "regime": clamp(regime.score_vector.get("trend", 0.0) - regime.score_vector.get("post_event_instability", 0.0)),
            "alignment": alignment,
            "structure": structure.cleanliness_score,
            "liquidity": liquidity.pressure_score,
            "sweep": sweep.reversal_probability if "reversal" in sweep.interpretation else sweep.continuation_probability,
            "event": 1.0 - event_risk.contamination_score,
            "instrument": instrument_health.health_score,
            "strategy": strat_score,
            "cross_asset": 1.0 - cross_asset.divergence_score,
            "execution": 1.0 - execution_burden,
            "context_penalty": 1.0 - context_penalty,
        }
        weights = {
            "regime": 0.08,
            "alignment": 0.14,
            "structure": 0.14,
            "liquidity": 0.10,
            "sweep": 0.10,
            "event": 0.10,
            "instrument": 0.12,
            "strategy": 0.12,
            "cross_asset": 0.05,
            "execution": 0.05,
            "context_penalty": 0.10,
        }
        raw_quality = clamp(sum(contrib[k] * w for k, w in weights.items()))
        uncertainty_score = uncertainty.uncertainty_score if uncertainty else clamp(context_penalty)
        quality_score = clamp(raw_quality * (1.0 - 0.35 * uncertainty_score))
        approval = clamp(quality_score * (1.0 - 0.45 * uncertainty_score))

        label = "elite" if quality_score > 0.8 else "high" if quality_score > 0.66 else "medium" if quality_score > 0.48 else "low"
        size_hint = clamp(0.35 + quality_score - 0.55 * uncertainty_score, 0.2, 1.5)
        positive = [k for k, v in contrib.items() if v >= 0.65 and k != "context_penalty"]
        negative = [k for k, v in contrib.items() if v <= 0.4 or (k == "context_penalty" and v < 0.6)]
        rationale = [Evidence(code, weights[code], value, "trade quality contribution") for code, value in contrib.items()]

        return TradeQualityState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - uncertainty_score),
            sources=["intelligence_engines"],
            rationale=rationale,
            quality_score=quality_score,
            approval_confidence=approval,
            cleanliness_score=structure.cleanliness_score,
            uncertainty_score=uncertainty_score,
            quality_label=label,
            size_multiplier=size_hint,
            contributions=contrib,
            alignment_score=alignment,
            context_penalty_score=context_penalty,
            execution_burden_score=execution_burden,
            size_multiplier_hint=size_hint,
            positive_factors=positive,
            negative_factors=negative,
        )
