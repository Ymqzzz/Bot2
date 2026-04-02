import numpy as np

from app.ml.config import RewardWeights
from app.ml.reward_engine import RewardEngine
from app.ml.training.env import EnvRow, TradingMetaEnv


def test_env_step_semantics():
    rows = [
        EnvRow(observation=np.array([0.0, 1.0], dtype=np.float32), has_candidate=True, in_position=False, risk_deterioration=False, metrics={"equity_change": 0.1}),
        EnvRow(observation=np.array([0.1, 0.8], dtype=np.float32), has_candidate=True, in_position=False, risk_deterioration=False, metrics={"equity_change": -0.1}),
    ]
    env = TradingMetaEnv(rows=rows, reward_engine=RewardEngine(RewardWeights()))
    obs, info = env.reset()
    assert obs.shape == (2,)
    _, reward, terminated, truncated, _ = env.step(1)
    assert isinstance(reward, float)
    assert not truncated
    assert not terminated
