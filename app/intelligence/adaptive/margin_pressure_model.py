from __future__ import annotations

from app.intelligence.base import clamp


class MarginPressureModel:
    """Models how volatility and concentration compress available margin."""

    def project_margin_compression(
        self,
        *,
        realized_vol: float,
        vol_percentile: float,
        correlation_stress: float,
        concentration: float,
    ) -> float:
        vol_term = clamp(realized_vol * 0.45 + vol_percentile * 0.55)
        structure_term = clamp(correlation_stress * 0.6 + concentration * 0.4)
        compression = clamp(0.35 * vol_term + 0.65 * structure_term)
        return compression

    def incremental_margin(self, *, notional: float, leverage: float, compression: float) -> float:
        effective_leverage = max(1.0, leverage * (1.0 - compression * 0.55))
        return notional / effective_leverage
