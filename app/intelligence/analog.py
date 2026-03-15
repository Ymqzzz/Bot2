from __future__ import annotations

from statistics import mean

from app.intelligence.base import clamp
from app.intelligence.models import AnalogSimilarityState, Evidence, MarketIntelligenceSnapshot


class AnalogEngine:
    def compute(self, snapshot: MarketIntelligenceSnapshot, history: list[dict], strategy: str) -> AnalogSimilarityState:
        if not history:
            return AnalogSimilarityState(
                timestamp=snapshot.timestamp,
                instrument=snapshot.instrument,
                trace_id=snapshot.trace_id,
                confidence=0.1,
                sources=["analog_history"],
                rationale=[Evidence("history", 1.0, 0.0, "no historical analogs")],
                comparable_cases=0,
                analog_confidence=0.0,
                insufficient_history_flag=True,
            )

        scored: list[tuple[float, dict]] = []
        for case in history:
            score = 0.0
            score += 0.35 if case.get("regime") == snapshot.regime.label else 0.1
            score += 0.25 * (1.0 - abs(float(case.get("alignment", 0.5)) - snapshot.mtf_bias.alignment_score))
            score += 0.2 * (1.0 if case.get("strategy") == strategy else 0.4)
            score += 0.2 * (1.0 - abs(float(case.get("quality", 0.5)) - snapshot.trade_quality.quality_score))
            scored.append((clamp(score), case))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: min(20, len(scored))]
        outcomes = [float(case.get("outcome", 0.0)) for _, case in top]
        similarity = mean([s for s, _ in top]) if top else 0.0

        return AnalogSimilarityState(
            timestamp=snapshot.timestamp,
            instrument=snapshot.instrument,
            trace_id=snapshot.trace_id,
            confidence=similarity,
            sources=["analog_history"],
            rationale=[Evidence("similarity", 1.0, similarity, "nearest analog score")],
            similarity_score=similarity,
            comparable_cases=len(top),
            avg_outcome=mean(outcomes) if outcomes else 0.0,
            analog_confidence=clamp(similarity * min(1.0, len(top) / 10.0)),
            insufficient_history_flag=len(top) < 5,
        )
