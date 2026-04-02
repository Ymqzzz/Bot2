from __future__ import annotations

from dataclasses import dataclass

from app.ml.rl_modes import RLMode


@dataclass(frozen=True)
class DriftStatus:
    psi: float
    action_rate_shift: float
    reward_shift: float
    should_downgrade: bool


def population_stability_index(expected: list[float], observed: list[float]) -> float:
    eps = 1e-8
    total = 0.0
    for e, o in zip(expected, observed):
        e2 = max(e, eps)
        o2 = max(o, eps)
        total += (o2 - e2) * (0.0 if e2 == o2 else __import__("math").log(o2 / e2))
    return float(total)


def evaluate_drift(expected_hist: list[float], observed_hist: list[float], action_rate_shift: float, reward_shift: float, psi_threshold: float) -> DriftStatus:
    psi = population_stability_index(expected_hist, observed_hist)
    should_downgrade = psi > psi_threshold or action_rate_shift > 0.4 or reward_shift < -0.5
    return DriftStatus(psi=psi, action_rate_shift=action_rate_shift, reward_shift=reward_shift, should_downgrade=should_downgrade)


def downgrade_mode(current_mode: RLMode, drift: DriftStatus) -> RLMode:
    if not drift.should_downgrade:
        return current_mode
    if current_mode == RLMode.ACTIVE:
        return RLMode.ADVISORY
    if current_mode == RLMode.ADVISORY:
        return RLMode.SHADOW
    return RLMode.SHADOW
