from __future__ import annotations

from app.intelligence.base import clamp


class LiquidationStressProjection:
    """Approximates liquidation cascade risk under correlated adverse moves."""

    def cascade_risk(
        self,
        *,
        free_margin_after_fill: float,
        equity: float,
        stress_drawdown: float,
        correlation_stress: float,
    ) -> float:
        if equity <= 0:
            return 1.0
        headroom = clamp(free_margin_after_fill / equity)
        stress = clamp(stress_drawdown * 0.7 + correlation_stress * 0.3)
        return clamp(stress * (1.0 - headroom))
