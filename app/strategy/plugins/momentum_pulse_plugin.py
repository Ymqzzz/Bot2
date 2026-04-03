from __future__ import annotations

from app.models.schema import SignalCandidate


class MomentumPulsePlugin:
    def name(self) -> str:
        return "momentum_pulse"

    def generate(self, instrument: str, bars: list[dict], features: dict) -> SignalCandidate | None:
        momentum = float(features.get("momentum", 0.0))
        trend_regime = float(features.get("trend_regime", 0.0))
        atr = max(float(features.get("atr", 0.0)), 1e-9)
        px = float(bars[-1]["close"])
        trigger = 0.45
        if abs(momentum) < trigger or trend_regime < 0.45:
            return None
        side = "BUY" if momentum > 0 else "SELL"
        strength = min(1.0, abs(momentum) / 2.5)
        score = max(0.2, min(1.0, 0.55 * strength + 0.45 * trend_regime))
        stop = px - 1.6 * atr if side == "BUY" else px + 1.6 * atr
        tp = px + 2.4 * atr if side == "BUY" else px - 2.4 * atr
        return SignalCandidate(
            instrument,
            side,
            score,
            self.name(),
            px,
            stop,
            tp,
            {"momentum": momentum, "trend_regime": trend_regime},
        )
