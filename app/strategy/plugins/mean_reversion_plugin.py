from __future__ import annotations

from app.models.schema import SignalCandidate


class MeanReversionPlugin:
    def name(self) -> str:
        return "mean_reversion_z"

    def generate(self, instrument: str, bars: list[dict], features: dict) -> SignalCandidate | None:
        z = float(features.get("zscore", 0.0))
        reversion_pressure = float(features.get("reversion_pressure", 0.0))
        chop_regime = float(features.get("chop_regime", 0.0))
        atr = max(float(features.get("atr", 0.0)), 1e-9)
        px = float(bars[-1]["close"])
        if abs(z) < 1.5 or reversion_pressure < 0.2 or chop_regime < 0.2:
            return None
        side = "SELL" if z > 0 else "BUY"
        score = min(1.0, abs(z) / 4.4 + 0.35 * reversion_pressure + 0.2 * chop_regime)
        stop = px + 1.4 * atr if side == "SELL" else px - 1.4 * atr
        tp = px - 1.9 * atr if side == "SELL" else px + 1.9 * atr
        return SignalCandidate(
            instrument,
            side,
            score,
            self.name(),
            px,
            stop,
            tp,
            {"zscore": z, "reversion_pressure": reversion_pressure, "chop_regime": chop_regime},
        )
