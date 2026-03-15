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
        details: dict[str, dict[str, float | str | bool]] = {}
        rationale: list[Evidence] = []

        for name, stats in perf.items():
            sample = max(0.0, float(stats.get("sample_size", 0.0)))
            win = clamp(float(stats.get("win_rate", 0.5)))
            expectancy = clamp((float(stats.get("expectancy", 0.0) + 1.0) / 2.0))
            payoff = clamp(float(stats.get("payoff_ratio", 1.0)) / 2.5)
            drawdown = clamp(float(stats.get("drawdown", 0.2)))
            mae_eff = clamp(1.0 - float(stats.get("mae_ratio", 0.4)))
            slip_damage = clamp(float(stats.get("slippage_damage", 0.2)))
            false_pos = clamp(float(stats.get("false_positive_rate", 0.3)))
            reliability = clamp(sample / 80.0)
            base_score = clamp(
                0.2 * win + 0.2 * expectancy + 0.15 * payoff + 0.1 * mae_eff - 0.15 * drawdown - 0.1 * slip_damage - 0.1 * false_pos
            )
            score = clamp(base_score * reliability + (1.0 - reliability) * 0.55)

            label = "strong" if score > 0.72 else "degraded" if score < 0.42 else "stable"
            throttle = clamp(0.55 + 0.9 * score, 0.35, 1.35)
            disable = bool(sample >= 40 and score < 0.25)
            sample_quality = clamp(sample / 120.0)
            rank_penalty = clamp((0.55 - score) * 0.8) if score < 0.55 else 0.0
            size_penalty = clamp((0.5 - score) * 0.7) if score < 0.5 else 0.0

            scores[name] = score
            labels[name] = label
            throttles[name] = throttle
            disables[name] = disable
            details[name] = {
                "health_score": score,
                "health_label": label,
                "sample_quality_score": sample_quality,
                "throttle_multiplier": throttle,
                "rank_penalty": rank_penalty,
                "size_penalty": size_penalty,
                "disable_recommendation": disable,
            }
            rationale.append(Evidence(f"strategy_health_{name}", 1.0 / max(1, len(perf)), score, "sample-aware strategy health"))

        confidence = clamp(sum(min(float(s.get("sample_size", 0.0)), 80.0) for s in perf.values()) / (80.0 * max(1, len(perf))))
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
            health_details=details,
        )
