from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RegimeInstabilityPenalty:
    penalty: float
    size_cap: float
    unsafe_for_trend: bool


class RegimeInstabilityPenaltyModel:
    def compute(self, transition_risk: float, persistence_score: float, conflict_score: float) -> RegimeInstabilityPenalty:
        risk = max(0.0, min(1.0, transition_risk))
        persist = max(0.0, min(1.0, persistence_score))
        conflict = max(0.0, min(1.0, conflict_score))

        penalty = min(0.95, 0.50 * risk + 0.30 * (1.0 - persist) + 0.20 * conflict)
        size_cap = max(0.25, 1.0 - penalty)
        unsafe = penalty > 0.40
        return RegimeInstabilityPenalty(penalty=penalty, size_cap=size_cap, unsafe_for_trend=unsafe)
