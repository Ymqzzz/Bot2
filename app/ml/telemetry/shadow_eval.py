from __future__ import annotations


def shadow_delta(baseline_reward: float, rl_counterfactual_reward: float) -> float:
    return rl_counterfactual_reward - baseline_reward
