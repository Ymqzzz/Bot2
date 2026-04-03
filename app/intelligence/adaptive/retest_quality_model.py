from __future__ import annotations

from app.intelligence.base import clamp


class RetestQualityModel:
    def score(self, *, setup_quality_now: float, setup_quality_prev: float, regime_improvement: float) -> float:
        quality_gain = clamp(setup_quality_now - setup_quality_prev + 0.5)
        return clamp(quality_gain * 0.65 + clamp(regime_improvement) * 0.35)
