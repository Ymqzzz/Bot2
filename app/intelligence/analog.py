from __future__ import annotations

from statistics import mean, pstdev

from app.intelligence.base import clamp
from app.intelligence.models import AnalogSimilarityState, Evidence, MarketIntelligenceSnapshot


class AnalogEngine:
    def compute(self, snapshot: MarketIntelligenceSnapshot, history: list[dict]) -> AnalogSimilarityState:
        if not history:
            return AnalogSimilarityState(
                timestamp=snapshot.timestamp,
                instrument=snapshot.instrument,
                trace_id=snapshot.trace_id,
                confidence=0.1,
                rationale=[Evidence("history", 1.0, 0.0, "no historical analogs")],
            )
        similarities: list[tuple[float, dict]] = []
        for case in history:
            sim = 1.0
            sim -= abs(case.get("alignment", 0.5) - snapshot.mtf_bias.alignment_score) * 0.3
            sim -= abs(case.get("health", 0.5) - snapshot.instrument_health.health_score) * 0.25
            sim -= abs(case.get("event", 0.5) - snapshot.event_risk.contamination_score) * 0.2
            sim -= 0.25 if case.get("regime") != snapshot.regime.label else 0.0
            similarities.append((clamp(sim), case))
        similarities.sort(key=lambda x: x[0], reverse=True)
        top = similarities[:20]
        outcomes = [c.get("outcome", 0.0) for _, c in top]
        score = mean([s for s, _ in top])
        return AnalogSimilarityState(
            timestamp=snapshot.timestamp,
            instrument=snapshot.instrument,
            trace_id=snapshot.trace_id,
            confidence=clamp(score),
            sources=["historical_intelligence_store"],
            rationale=[Evidence("similarity", 0.7, score, "nearest-neighbor similarity"), Evidence("sample", 0.3, float(len(top)), "comparable case count")],
            similarity_score=score,
            comparable_cases=len(top),
            avg_outcome=mean(outcomes) if outcomes else 0.0,
            outcome_dispersion=pstdev(outcomes) if len(outcomes) > 1 else 0.0,
            best_strategy_family=max((c.get("strategy", "unknown") for _, c in top), key=lambda n: sum(x.get("outcome", 0.0) for _, x in top if x.get("strategy") == n), default="unknown"),
            analog_confidence=clamp(score * min(1.0, len(top) / 12.0)),
        )
