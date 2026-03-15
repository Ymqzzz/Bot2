from __future__ import annotations

from statistics import mean, median, pstdev

from app.intelligence.base import clamp
from app.intelligence.models import AnalogSimilarityState, Evidence, MarketIntelligenceSnapshot


class AnalogEngine:
    WEIGHTS = {
        "regime": 0.15,
        "session": 0.05,
        "alignment": 0.14,
        "structure_phase": 0.12,
        "liquidity_context": 0.10,
        "sweep_type": 0.10,
        "spread": 0.10,
        "event": 0.09,
        "instrument_health": 0.08,
        "quality": 0.07,
    }

    def compute(self, snapshot: MarketIntelligenceSnapshot, history: list[dict]) -> AnalogSimilarityState:
        if not history:
            return AnalogSimilarityState(
                timestamp=snapshot.timestamp,
                instrument=snapshot.instrument,
                trace_id=snapshot.trace_id,
                confidence=0.1,
                rationale=[Evidence("history", 1.0, 0.0, "no historical analogs")],
                insufficient_history_flag=True,
            )

        similarities: list[tuple[float, dict]] = []
        for case in history:
            terms = {
                "regime": 1.0 if case.get("regime") == snapshot.regime.label else 0.3,
                "session": 1.0 if case.get("session", "any") == snapshot.instrument else 0.6,
                "alignment": 1.0 - abs(float(case.get("alignment", 0.5)) - snapshot.mtf_bias.alignment_score),
                "structure_phase": 1.0 if case.get("structure_phase") == snapshot.structure.current_phase else 0.45,
                "liquidity_context": 1.0 if case.get("liquidity_context") == snapshot.liquidity.liquidity_context_label else 0.5,
                "sweep_type": 1.0 if case.get("sweep_type") == snapshot.sweep.sweep_type else 0.5,
                "spread": 1.0 - abs(float(case.get("spread", 0.5)) - float(snapshot.trade_quality.execution_burden_score)),
                "event": 1.0 - abs(float(case.get("event", 0.5)) - snapshot.event_risk.contamination_score),
                "instrument_health": 1.0 - abs(float(case.get("health", 0.5)) - snapshot.instrument_health.health_score),
                "quality": 1.0 - abs(float(case.get("quality", 0.5)) - snapshot.trade_quality.quality_score),
            }
            sim = clamp(sum(clamp(terms[k]) * w for k, w in self.WEIGHTS.items()))
            similarities.append((sim, case))

        similarities.sort(key=lambda x: x[0], reverse=True)
        top = similarities[: min(25, len(similarities))]
        outcomes = [float(c.get("outcome", 0.0)) for _, c in top]
        wins = [1.0 if x > 0 else 0.0 for x in outcomes]
        payoffs = [float(c.get("payoff", 1.0)) for _, c in top]
        maes = [float(c.get("mae", 0.5)) for _, c in top]
        mfes = [float(c.get("mfe", 0.5)) for _, c in top]
        score = mean([s for s, _ in top])

        best_strategy = max(
            (c.get("strategy", "unknown") for _, c in top),
            key=lambda n: sum(float(x.get("outcome", 0.0)) for _, x in top if x.get("strategy") == n),
            default="unknown",
        )
        analog_conf = clamp(score * min(1.0, len(top) / 20.0))
        insufficient = len(top) < 5
        return AnalogSimilarityState(
            timestamp=snapshot.timestamp,
            instrument=snapshot.instrument,
            trace_id=snapshot.trace_id,
            confidence=clamp(score),
            sources=["historical_intelligence_store"],
            rationale=[
                Evidence("similarity", 0.6, score, "weighted nearest-neighbor similarity"),
                Evidence("sample", 0.4, float(len(top)), "matched analog case count"),
            ],
            similarity_score=score,
            comparable_cases=len(top),
            avg_outcome=mean(outcomes) if outcomes else 0.0,
            outcome_dispersion=pstdev(outcomes) if len(outcomes) > 1 else 0.0,
            best_strategy_family=best_strategy,
            analog_confidence=analog_conf,
            historical_win_rate=mean(wins) if wins else 0.0,
            historical_payoff_ratio=mean(payoffs) if payoffs else 0.0,
            historical_mae_median=median(maes) if maes else 0.0,
            historical_mfe_median=median(mfes) if mfes else 0.0,
            insufficient_history_flag=insufficient,
        )
