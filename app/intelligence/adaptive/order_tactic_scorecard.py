from __future__ import annotations

from app.intelligence.base import clamp


class OrderTacticScorecard:
    def penalty(self, *, tactic_success: float, adverse_selection: float) -> float:
        return clamp((1.0 - tactic_success) * 0.65 + adverse_selection * 0.35)
