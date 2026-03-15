from __future__ import annotations

from statistics import mean, median, pstdev

from app.intelligence.base import clamp
from app.intelligence.models import AnalogSimilarityState, Evidence, MarketIntelligenceSnapshot


class AnalogEngine:
    WEIGHTS = {
        "regime": 0.18,
        "alignment": 0.12,
        "phase": 0.15,
        "liquidity": 0.1,
        "sweep": 0.1,
        "spread": 0.08,
        "event": 0.1,
        "strategy": 0.07,
        "quality": 0.1,
    }

    def _similarity(self, case: dict, snapshot: MarketIntelligenceSnapshot, strategy: str) -> float:
        checks = {
            "regime": 1.0 if case.get("regime") == snapshot.regime.label else 0.0,
            "alignment": 1.0 - abs(float(case.get("alignment", 0.5)) - snapshot.mtf_bias.alignment_score),
            "phase": 1.0 if case.get("phase") == snapshot.structure.current_phase else 0.0,
            "liquidity": 1.0 - abs(float(case.get("liquidity", 0.5)) - snapshot.liquidity.pressure_score),
            "sweep": 1.0 if case.get("sweep_type") == snapshot.sweep.sweep_type else 0.3,
            "spread": 1.0 - abs(float(case.get("spread", 0.5)) - snapshot.trade_quality.execution_burden_score),
            "event": 1.0 - abs(float(case.get("event", 0.5)) - snapshot.event_risk.contamination_score),
            "strategy": 1.0 if case.get("strategy") == strategy else 0.35,
            "quality": 1.0 - abs(float(case.get("quality", 0.5)) - snapshot.trade_quality.trade_quality_score),
        }
        return clamp(sum(clamp(checks[k]) * self.WEIGHTS[k] for k in self.WEIGHTS))

    def compute(self, snapshot: MarketIntelligenceSnapshot, history: list[dict], strategy: str) -> AnalogSimilarityState:
        if not history:
            return AnalogSimilarityState(
                timestamp=snapshot.timestamp,
                instrument=snapshot.instrument,
                trace_id=snapshot.trace_id,
                confidence=0.1,
                rationale=[Evidence("history", 1.0, 0.0, "no historical analogs")],
                insufficient_history_flag=True,
            )

        sims = sorted(((self._similarity(case, snapshot, strategy), case) for case in history), key=lambda x: x[0], reverse=True)
        top_n = min(25, max(5, len(sims) // 3))
        top = sims[:top_n]
        outcomes = [float(c.get("outcome", 0.0)) for _, c in top]
        wins = [1.0 if o > 0 else 0.0 for o in outcomes]
        payoffs = [float(c.get("payoff", max(float(c.get("outcome", 0.0)), 0.0))) for _, c in top]
        maes = [abs(float(c.get("mae", 0.0))) for _, c in top]
        mfes = [abs(float(c.get("mfe", 0.0))) for _, c in top]
        score = mean([s for s, _ in top]) if top else 0.0

        return AnalogSimilarityState(
            timestamp=snapshot.timestamp,
            instrument=snapshot.instrument,
            trace_id=snapshot.trace_id,
            confidence=clamp(score),
            sources=["historical_intelligence_store"],
            rationale=[Evidence("similarity", 0.7, score, "weighted analog similarity"), Evidence("sample", 0.3, float(len(top)), "comparable case count")],
            similarity_score=score,
            comparable_cases=len(top),
            avg_outcome=mean(outcomes) if outcomes else 0.0,
            outcome_dispersion=pstdev(outcomes) if len(outcomes) > 1 else 0.0,
            best_strategy_family=max((c.get("strategy", "unknown") for _, c in top), key=lambda n: sum(x.get("outcome", 0.0) for _, x in top if x.get("strategy") == n), default="unknown"),
            analog_confidence=clamp(score * min(1.0, len(top) / 20.0)),
            matched_case_count=len(history),
            top_match_count_used=len(top),
            historical_expectancy=mean(outcomes) if outcomes else 0.0,
            historical_win_rate=mean(wins) if wins else 0.0,
            historical_payoff_ratio=mean(payoffs) if payoffs else 0.0,
            historical_mae_median=median(maes) if maes else 0.0,
            historical_mfe_median=median(mfes) if mfes else 0.0,
            insufficient_history_flag=len(history) < 8,
        )
