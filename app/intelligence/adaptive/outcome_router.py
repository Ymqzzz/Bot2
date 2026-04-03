from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptiveOutcomeRoute:
    action: str
    confidence_multiplier: float
    size_multiplier: float


class AdaptiveOutcomeRouter:
    def route(self, *, approved: bool, confidence_delta: float, fragility: float, vetoed: bool) -> AdaptiveOutcomeRoute:
        if vetoed:
            return AdaptiveOutcomeRoute(action="block", confidence_multiplier=0.0, size_multiplier=0.0)
        if not approved:
            return AdaptiveOutcomeRoute(action="defer", confidence_multiplier=0.5, size_multiplier=0.4)
        if fragility > 0.55 or confidence_delta < 0.0:
            return AdaptiveOutcomeRoute(action="throttle", confidence_multiplier=0.8, size_multiplier=0.65)
        return AdaptiveOutcomeRoute(action="approve", confidence_multiplier=1.0, size_multiplier=1.0)
