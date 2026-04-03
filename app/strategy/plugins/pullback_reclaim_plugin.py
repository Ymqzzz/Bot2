from __future__ import annotations

from app.models.schema import SignalCandidate


class PullbackReclaimPlugin:
    def name(self) -> str:
        return "pullback_reclaim"

    def generate(self, instrument: str, bars: list[dict], features: dict) -> SignalCandidate | None:
        if len(bars) < 30:
            return None
        close = float(bars[-1]["close"])
        ema_fast = float(features.get("ema_fast", close))
        ema_slow = float(features.get("ema_slow", close))
        zscore = float(features.get("zscore", 0.0))
        trend_regime = float(features.get("trend_regime", 0.0))
        atr = max(float(features.get("atr", 0.0)), 1e-9)
        if trend_regime < 0.4:
            return None
        if ema_fast > ema_slow and -1.9 <= zscore <= -0.35:
            side = "BUY"
        elif ema_fast < ema_slow and 0.35 <= zscore <= 1.9:
            side = "SELL"
        else:
            return None
        score = max(0.2, min(1.0, 0.6 * trend_regime + 0.4 * (1.0 - min(1.0, abs(zscore) / 2.0))))
        stop = close - 1.45 * atr if side == "BUY" else close + 1.45 * atr
        tp = close + 2.2 * atr if side == "BUY" else close - 2.2 * atr
        return SignalCandidate(
            instrument,
            side,
            score,
            self.name(),
            close,
            stop,
            tp,
            {"zscore": zscore, "trend_regime": trend_regime},
        )
