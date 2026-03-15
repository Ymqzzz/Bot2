from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class SizingDiagnostics:
    signed_units: int
    confidence_multiplier: float
    spread_multiplier: float
    stop_volatility_multiplier: float
    dislocation_multiplier: float
    portfolio_budget_pct: float
    max_units_cap: int
    capped: bool

    def to_dict(self) -> dict:
        return asdict(self)


class PositionSizer:
    """Conservative position sizing with explicit diagnostics."""

    def __init__(self, max_notional_nav_multiple: float = 0.25):
        self.max_notional_nav_multiple = float(max_notional_nav_multiple)

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, float(x)))

    @staticmethod
    def _estimate_open_risk_pct(open_positions: list[dict], nav: float) -> float:
        nav = max(float(nav), 1e-9)
        total = 0.0
        for p in open_positions:
            try:
                units = abs(float(p.get("units", 0.0)))
                entry = float(p.get("entry_price", 0.0))
                stop = float(p.get("stop_loss", entry))
            except (TypeError, ValueError):
                continue
            total += abs(entry - stop) * units / nav
        return max(0.0, total)

    def compute_units(
        self,
        side: str,
        nav: float,
        entry_price: float,
        stop_loss: float,
        atr: float,
        dislocation: float,
        spread_pctile: float,
        confidence: float,
        open_positions: list[dict],
        daily_risk_pct: float,
        cluster_risk_pct: float,
    ) -> SizingDiagnostics:
        nav_f = max(float(nav), 0.0)
        if nav_f <= 0:
            return SizingDiagnostics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, False)

        stop_distance = max(abs(float(entry_price) - float(stop_loss)), 1e-9)
        atr_f = max(float(atr), 1e-9)

        # Remaining account risk budget after open risk.
        open_risk_pct = self._estimate_open_risk_pct(open_positions, nav_f)
        remaining_daily_risk = max(0.0, float(daily_risk_pct) - open_risk_pct)
        portfolio_budget_pct = min(float(cluster_risk_pct), remaining_daily_risk * 0.50)

        confidence_multiplier = self._clamp(0.35 + 0.65 * float(confidence), 0.20, 1.00)
        spread_multiplier = self._clamp(1.0 - 0.60 * (float(spread_pctile) / 100.0), 0.20, 1.00)
        dislocation_multiplier = self._clamp(1.0 + 0.35 * max(0.0, float(dislocation) - 1.0), 1.0, 2.0)

        # Intentional safety: tighter stops relative to ATR reduce size to avoid noise-stop churn.
        stop_volatility_multiplier = self._clamp(stop_distance / atr_f, 0.20, 2.00)

        risk_budget_notional = nav_f * portfolio_budget_pct
        denom = max(atr_f * 10_000.0 * dislocation_multiplier, 1e-9)
        raw_units = risk_budget_notional * confidence_multiplier * spread_multiplier * stop_volatility_multiplier / denom

        max_units_cap = int(max(0.0, nav_f * self.max_notional_nav_multiple / max(float(entry_price), 1e-6)))
        units_abs = int(max(0.0, raw_units))
        capped = units_abs > max_units_cap
        units_abs = min(units_abs, max_units_cap)

        signed_units = units_abs if str(side).upper() == "BUY" else -units_abs
        return SizingDiagnostics(
            signed_units=signed_units,
            confidence_multiplier=confidence_multiplier,
            spread_multiplier=spread_multiplier,
            stop_volatility_multiplier=stop_volatility_multiplier,
            dislocation_multiplier=dislocation_multiplier,
            portfolio_budget_pct=portfolio_budget_pct,
            max_units_cap=max_units_cap,
            capped=capped,
        )
