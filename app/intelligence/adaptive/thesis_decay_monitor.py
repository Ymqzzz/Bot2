from __future__ import annotations

from app.intelligence.base import clamp


class ThesisDecayMonitor:
    def estimate_decay(self, *, age_bars: float, regime_instability: float) -> float:
        age_term = clamp(age_bars / 120.0)
        return clamp(age_term * 0.65 + clamp(regime_instability) * 0.35)
