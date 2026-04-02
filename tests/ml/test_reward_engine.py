from app.ml.config import RewardWeights
from app.ml.reward_engine import RewardEngine


def test_reward_component_inspectability():
    engine = RewardEngine(RewardWeights())
    reward = engine.compute(
        {
            "equity_change": 1.0,
            "realized_vol": 0.5,
            "downside_vol": 0.6,
            "fill_quality": 0.2,
            "signal_precision_delta": 0.1,
            "transaction_cost": 0.05,
            "slippage": 0.02,
            "drawdown_delta": 0.03,
        }
    )
    assert reward.pnl_component > 0
    assert reward.transaction_cost_penalty > 0
    assert isinstance(reward.total, float)
