from __future__ import annotations

from app.intelligence.base import clamp


class TradeAttackSurface:
    def score(self, *, liquidity_thin: float, event_risk: float, regime_instability: float) -> float:
        return clamp(liquidity_thin * 0.4 + event_risk * 0.25 + regime_instability * 0.35)
