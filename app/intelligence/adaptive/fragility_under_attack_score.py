from __future__ import annotations

from app.intelligence.base import clamp


class FragilityUnderAttackScore:
    def score(self, *, top_modes: list[tuple[str, float]], resilience: float) -> float:
        if not top_modes:
            return 0.0
        avg_top = sum(v for _, v in top_modes[:3]) / min(3, len(top_modes))
        return clamp(avg_top * (1.0 - clamp(resilience)))
