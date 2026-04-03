from __future__ import annotations

from app.intelligence.base import clamp


class FollowthroughQualityScorer:
    def score(self, *, initial_thrust: float, sustained_move: float, stop_zone_probes: int) -> float:
        thrust_term = clamp(initial_thrust)
        sustain_term = clamp(sustained_move)
        probe_penalty = clamp(stop_zone_probes / 5.0)
        return clamp((thrust_term * 0.45 + sustain_term * 0.55) * (1.0 - 0.5 * probe_penalty))
