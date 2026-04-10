from datetime import datetime

from app.intelligence.base import EngineInput
from app.intelligence.strategy_health import StrategyHealthEngine


def _engine_input(context: dict) -> EngineInput:
    return EngineInput(
        timestamp=datetime(2026, 1, 1),
        instrument="EURUSD",
        trace_id="test-trace",
        features={},
        bars=[],
        context=context,
    )


def test_strategy_health_details_stay_in_sync_with_top_level_fields() -> None:
    state = StrategyHealthEngine().compute(
        _engine_input(
            {
                "strategy_performance": {
                    "trend": {
                        "sample_size": 50,
                        "win_rate": 0.62,
                        "expectancy": 0.2,
                        "payoff_ratio": 1.5,
                        "drawdown": 0.15,
                        "mae_ratio": 0.35,
                        "slippage_damage": 0.1,
                        "false_positive_rate": 0.2,
                    }
                }
            }
        )
    )

    detail = state.health_details["trend"]
    assert state.strategy_scores["trend"] == detail["health_score"]
    assert state.strategy_labels["trend"] == detail["health_label"]
    assert state.throttle_multipliers["trend"] == detail["throttle_multiplier"]
    assert state.rank_penalties["trend"] == detail["rank_penalty"]
    assert state.size_penalties["trend"] == detail["size_penalty"]
    assert state.sample_quality_scores["trend"] == detail["sample_quality_score"]


def test_strategy_disable_requires_opt_in_flag() -> None:
    perf = {
        "mean_reversion": {
            "sample_size": 80,
            "win_rate": 0.0,
            "expectancy": -1.0,
            "payoff_ratio": 0.0,
            "drawdown": 1.0,
            "mae_ratio": 1.0,
            "slippage_damage": 1.0,
            "false_positive_rate": 1.0,
        }
    }

    not_opted_in = StrategyHealthEngine().compute(_engine_input({"strategy_performance": perf}))
    opted_in = StrategyHealthEngine().compute(
        _engine_input({"strategy_performance": perf, "allow_strategy_disable": True})
    )

    assert not not_opted_in.disable_flags["mean_reversion"]
    assert opted_in.disable_flags["mean_reversion"]
