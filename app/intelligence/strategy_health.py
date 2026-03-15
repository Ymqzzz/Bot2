from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, StrategyHealthState


class StrategyHealthEngine:
    def compute(self, data: EngineInput) -> StrategyHealthState:
        perf = data.context.get("strategy_performance", {})
        scores: dict[str, float] = {}
        labels: dict[str, str] = {}
        throttles: dict[str, float] = {}
        disables: dict[str, bool] = {}
        rationale: list[Evidence] = []
        for name, stats in perf.items():
            sample = float(stats.get("sample_size", 0.0))
            win = clamp(float(stats.get("win_rate", 0.5)))
            expectancy = clamp((float(stats.get("expectancy", 0.0)) + 1.0) / 2.0)
            drawdown = clamp(float(stats.get("drawdown", 0.2)))
            reliability = clamp(sample / 40.0)
            score = clamp((0.45 * win + 0.4 * expectancy - 0.35 * drawdown) * reliability + 0.5 * (1.0 - reliability))
            scores[name] = score
            labels[name] = "strong" if score > 0.7 else "degraded" if score < 0.45 else "stable"
            throttles[name] = clamp(0.4 + 0.9 * score, 0.25, 1.25)
            disables[name] = sample >= 20 and score < 0.28
            rationale.append(Evidence(f"{name}_score", 1.0 / max(1, len(perf)), score, "contextual strategy health score"))

        confidence = clamp(sum(min(float(s.get("sample_size", 0.0)), 40.0) for s in perf.values()) / (40.0 * max(1, len(perf))))
        return StrategyHealthState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=confidence,
            sources=["internal_performance"],
            rationale=rationale,
            strategy_scores=scores,
            strategy_labels=labels,
            throttle_multipliers=throttles,
            disable_flags=disables,
        )
