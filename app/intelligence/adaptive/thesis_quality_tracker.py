from __future__ import annotations

from app.intelligence.base import clamp


class ThesisQualityTracker:
    def quality(self, *, win_rate: float, expectancy: float, fragility: float, decay: float) -> float:
        wr = clamp(win_rate)
        ex = clamp((expectancy + 1.0) / 2.0)
        risk = clamp(fragility * 0.6 + decay * 0.4)
        return clamp((wr * 0.45 + ex * 0.55) * (1.0 - risk * 0.5))
