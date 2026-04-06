from __future__ import annotations

from app.models.schema import SignalCandidate


class TrendPlugin:
    def name(self) -> str:
        return "trend_ema"

    def generate(self, instrument: str, bars: list[dict], features: dict) -> SignalCandidate | None:
        slope = float(features.get("ema_slope", 0.0))
        trend_alignment = float(features.get("trend_alignment", 0.0))
        trend_consistency = float(features.get("trend_consistency", 0.0))
        atr = max(float(features.get("atr", 0.0)), 1e-9)
        px = float(bars[-1]["close"])
        if abs(slope) < 0.00001 or abs(trend_alignment) < 0.08 or trend_consistency < 0.03:
            return None
        side = "BUY" if slope > 0 else "SELL"
        score = min(1.0, abs(slope) * 3000.0 + 0.4 * abs(trend_alignment) + 0.2 * trend_consistency)
        stop = px - 1.8 * atr if side == "BUY" else px + 1.8 * atr
        tp = px + 2.6 * atr if side == "BUY" else px - 2.6 * atr
        return SignalCandidate(
            instrument,
            side,
            score,
            self.name(),
            px,
            stop,
            tp,
            {"ema_slope": slope, "trend_alignment": trend_alignment, "trend_consistency": trend_consistency},
        )
