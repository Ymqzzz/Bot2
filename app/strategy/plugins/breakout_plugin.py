from __future__ import annotations

from app.models.schema import SignalCandidate


class BreakoutPlugin:
    def name(self) -> str:
        return "range_breakout"

    def generate(self, instrument: str, bars: list[dict], features: dict) -> SignalCandidate | None:
        if len(bars) < 25:
            return None
        highs = [float(b["high"]) for b in bars[-20:]]
        lows = [float(b["low"]) for b in bars[-20:]]
        px = float(bars[-1]["close"])
        atr = max(float(features.get("atr", 0.0)), 1e-9)
        hi, lo = max(highs[:-1]), min(lows[:-1])
        if px > hi:
            side = "BUY"
        elif px < lo:
            side = "SELL"
        else:
            return None
        score = min(1.0, abs(px - (hi if side == 'BUY' else lo)) / max(atr, 1e-6))
        stop = px - 2.0 * atr if side == "BUY" else px + 2.0 * atr
        tp = px + 3.0 * atr if side == "BUY" else px - 3.0 * atr
        return SignalCandidate(instrument, side, score, self.name(), px, stop, tp, {"range_hi": hi, "range_lo": lo})
