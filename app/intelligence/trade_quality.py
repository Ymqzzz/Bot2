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
        calibrated_score: float,
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
        portfolio_conflict: float = 0.0,
    ) -> TradeQualityState:
        strat_score = strategy_health.strategy_scores.get(candidate_strategy, 0.5)
        alignment = clamp(mtf.alignment_score * (1.0 - 0.4 * mtf.conflict_score))
        structure_clean = clamp(structure.cleanliness_score * (1.0 - 0.4 * structure.messiness_penalty))
        liquidity_quality = clamp((liquidity.pressure_score + (liquidity.all_pools[0].significance_score if liquidity.all_pools else 0.5)) / 2.0)
        sweep_quality = clamp(max(sweep.reversal_probability, sweep.continuation_probability))
        event_quality = 1.0 - clamp(event_risk.contamination_score)
        execution_burden = clamp(execution_cost)
        context_penalty = clamp(0.45 * mtf.conflict_score + 0.25 * structure.messiness_penalty + 0.2 * event_risk.contamination_score + 0.1 * portfolio_conflict)

        contrib = {
            "calibrated_score": clamp(calibrated_score),
            "regime": clamp(regime.score_vector.get("trend", 0.5) - regime.score_vector.get("post_event_instability", 0.0)),
            "alignment": alignment,
            "structure": structure_clean,
            "liquidity": liquidity_quality,
            "sweep": sweep_quality,
            "event": event_quality,
            "instrument": instrument_health.health_score,
            "strategy": strat_score,
            "cross_asset": 1.0 - cross_asset.divergence_score,
            "execution": 1.0 - execution_burden,
            "context_penalty": 1.0 - context_penalty,
        }
        weights = {
            "calibrated_score": 0.1,
            "regime": 0.08,
            "alignment": 0.14,
            "structure": 0.14,
            "liquidity": 0.1,
            "sweep": 0.08,
            "event": 0.1,
            "instrument": 0.1,
            "strategy": 0.1,
            "cross_asset": 0.05,
            "execution": 0.05,
            "context_penalty": 0.06,
        }
        raw_quality = clamp(sum(contrib[k] * weights[k] for k in weights))
        uncertainty_score = uncertainty.uncertainty_score if uncertainty else clamp(context_penalty)
        quality_score = clamp(raw_quality * (1.0 - 0.35 * uncertainty_score))
        approval = clamp(quality_score * (1.0 - 0.45 * uncertainty_score))

        label = "elite" if quality_score > 0.8 else "high" if quality_score > 0.66 else "medium" if quality_score > 0.48 else "low"
        size_hint = clamp(0.35 + quality_score - 0.55 * uncertainty_score, 0.2, 1.5)

        return TradeQualityState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - uncertainty_score),
            sources=["intelligence_engines"],
            rationale=[Evidence(code, weights[code], value, "trade quality contribution") for code, value in contrib.items()],
            quality_score=quality_score,
            approval_confidence=approval,
            cleanliness_score=structure_clean,
            uncertainty_score=uncertainty_score,
            quality_label=label,
            size_multiplier=size_hint,
            contributions=contrib,
            alignment_score=alignment,
            context_penalty_score=context_penalty,
            execution_burden_score=execution_burden,
            size_multiplier_hint=size_hint,
            positive_factors=[k for k, v in contrib.items() if v >= 0.65],
            negative_factors=[k for k, v in contrib.items() if v <= 0.4],
            trade_quality_score=quality_score,
            setup_cleanliness_score=structure_clean,
        )
