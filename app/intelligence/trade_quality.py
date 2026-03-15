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
        portfolio_conflict: float = 0.0,
    ) -> TradeQualityState:
        strat_score = strategy_health.strategy_scores.get(candidate_strategy, 0.5)
        alignment = clamp(mtf.alignment_score * (1.0 - 0.4 * mtf.conflict_score))
        structure_clean = clamp(structure.cleanliness_score * (1.0 - 0.4 * structure.messiness_penalty))
        liquidity_quality = clamp((liquidity.pressure_score + (liquidity.all_pools[0].significance_score if liquidity.all_pools else 0.5)) / 2.0)
        sweep_quality = clamp(max(sweep.reversal_probability, sweep.continuation_probability) * (1.0 if "ambiguous" not in sweep.sweep_type else 0.5))
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
        }
        weights = {
            "calibrated_score": 0.1,
            "regime": 0.08,
            "alignment": 0.14,
            "structure": 0.14,
            "liquidity": 0.08,
            "sweep": 0.08,
            "event": 0.1,
            "instrument": 0.1,
            "strategy": 0.1,
            "cross_asset": 0.04,
            "execution": 0.04,
        }
        raw_quality = clamp(sum(contrib[k] * weights[k] for k in weights))
        tradability = clamp(raw_quality - 0.35 * context_penalty - 0.25 * execution_burden)
        uncertainty = clamp(0.4 * mtf.conflict_score + 0.25 * structure.messiness_penalty + 0.2 * (1.0 - sweep.sweep_confidence) + 0.15 * event_risk.contamination_score)
        approval = clamp(tradability * (1.0 - 0.55 * uncertainty))
        label = "elite" if tradability > 0.78 else "high" if tradability > 0.62 else "medium" if tradability > 0.45 else "low"
        size = clamp(0.35 + tradability - 0.5 * uncertainty, 0.15, 1.5)

        positives = [k for k, v in contrib.items() if v > 0.65]
        negatives = [k for k, v in contrib.items() if v < 0.4]
        rationale = [Evidence(code, weights.get(code, 0.0), value, "trade quality contribution") for code, value in contrib.items()]

        return TradeQualityState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=clamp(1.0 - uncertainty),
            sources=["intelligence_engines"],
            rationale=rationale,
            quality_score=tradability,
            approval_confidence=approval,
            cleanliness_score=structure_clean,
            uncertainty_score=uncertainty,
            quality_label=label,
            size_multiplier=size,
            contributions=contrib,
            trade_quality_score=tradability,
            setup_cleanliness_score=structure_clean,
            alignment_score=alignment,
            context_penalty_score=context_penalty,
            execution_burden_score=execution_burden,
            size_multiplier_hint=size,
            positive_factors=positives,
            negative_factors=negatives,
        )
