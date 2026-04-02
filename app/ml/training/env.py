from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.ml.action_space import MetaAction
from app.ml.reward_engine import RewardEngine

try:
    import gymnasium as gym
    from gymnasium import spaces
except Exception:  # pragma: no cover
    class _CompatEnv:
        metadata = {}

        def reset(self, *, seed=None):
            self._seed = seed

    class _Box:
        def __init__(self, low, high, shape, dtype):
            self.low = low
            self.high = high
            self.shape = shape
            self.dtype = dtype

    class _Discrete:
        def __init__(self, n):
            self.n = n

    class _Spaces:
        Box = _Box
        Discrete = _Discrete

    class _CompatGym:
        Env = _CompatEnv

    gym = _CompatGym()
    spaces = _Spaces()


@dataclass(frozen=True)
class EnvRow:
    observation: np.ndarray
    has_candidate: bool
    in_position: bool
    risk_deterioration: bool
    metrics: dict[str, float]


class TradingMetaEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, rows: list[EnvRow], reward_engine: RewardEngine):
        super().__init__()
        if not rows:
            raise ValueError("rows cannot be empty")
        self.rows = rows
        self.reward_engine = reward_engine
        obs_dim = int(rows[0].observation.shape[0])
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Discrete(len(MetaAction))
        self._idx = 0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._idx = 0
        return self.rows[self._idx].observation, {"idx": self._idx}

    def step(self, action: int):
        row = self.rows[self._idx]
        reward_metrics = dict(row.metrics)
        if action == int(MetaAction.VETO_TRADE):
            reward_metrics["overtrade_score"] = max(0.0, reward_metrics.get("overtrade_score", 0.0) - 0.1)
        if action == int(MetaAction.INCREASE_SIZE_25_WITHIN_CAPS):
            reward_metrics["drawdown_delta"] = reward_metrics.get("drawdown_delta", 0.0) * 1.2
        reward = self.reward_engine.compute(reward_metrics).total
        self._idx += 1
        terminated = self._idx >= len(self.rows)
        truncated = False
        next_obs = self.rows[min(self._idx, len(self.rows) - 1)].observation
        info = {"idx": self._idx, "reward_components": self.reward_engine.compute(reward_metrics).__dict__}
        return next_obs, float(reward), terminated, truncated, info
