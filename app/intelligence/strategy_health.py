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
        sample_quality: dict[str, float] = {}
        rank_penalties: dict[str, float] = {}
        size_penalties: dict[str, float] = {}
        rationale: list[Evidence] = []

        for name, stats in perf.items():
            sample = float(stats.get("sample_size", 0.0))
            sample_q = clamp(sample / 60.0)
            win = clamp(float(stats.get("win_rate", 0.5)))
            expectancy = clamp((float(stats.get("expectancy", 0.0)) + 1.0) / 2.0)
            payoff = clamp(float(stats.get("payoff_ratio", 1.0)) / 2.5)
            mae_eff = clamp(1.0 - float(stats.get("mae_median", 0.5)))
            slip_damage = clamp(float(stats.get("slippage_damage", 0.1)))
            drawdown = clamp(float(stats.get("drawdown", 0.2)))
            false_positive = clamp(float(stats.get("false_positive_rate", 0.2)))
            drift = clamp(abs(float(stats.get("live_baseline_drift", 0.0))))

            base = (
                0.24 * win
                + 0.20 * expectancy
                + 0.14 * payoff
                + 0.10 * mae_eff
                - 0.16 * drawdown
                - 0.08 * false_positive
                - 0.05 * slip_damage
                - 0.03 * drift
            )
            score = clamp(base * sample_q + 0.5 * (1.0 - sample_q))
            scores[name] = score
            sample_quality[name] = sample_q

            labels[name] = "strong" if score > 0.72 else "degraded" if score < 0.42 else "stable"
            throttles[name] = clamp(0.5 + 0.9 * score, 0.3, 1.3)
            rank_penalties[name] = clamp((0.55 - score) * 1.3) if score < 0.55 else 0.0
            size_penalties[name] = clamp((0.6 - score) * 1.2) if score < 0.6 else 0.0
            disables[name] = bool(data.context.get("allow_strategy_disable", False) and sample >= 35 and score < 0.22)
            rationale.append(Evidence(f"{name}_health_score", 1.0 / max(1, len(perf)), score, "sample-aware strategy health score"))

        confidence = clamp(sum(min(float(s.get("sample_size", 0.0)), 60.0) for s in perf.values()) / (60.0 * max(1, len(perf))))
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
            sample_quality_scores=sample_quality,
            rank_penalties=rank_penalties,
            size_penalties=size_penalties,
        )
