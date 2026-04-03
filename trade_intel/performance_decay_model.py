from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PerformanceDecayModel:
    half_life_trades: float = 40.0

    def decay_weight(self, age_trades: int) -> float:
        age = max(0, int(age_trades))
        return 0.5 ** (age / max(1.0, self.half_life_trades))

    def ewma(self, current: float, new_value: float, age_trades: int = 1) -> float:
        w = self.decay_weight(age_trades)
        alpha = 1.0 - w
        return (1.0 - alpha) * current + alpha * new_value
