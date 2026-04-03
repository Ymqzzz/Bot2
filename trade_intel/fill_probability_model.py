from __future__ import annotations


class FillProbabilityModel:
    def estimate(self, spread_bps: float, volatility_score: float, latency_risk: float, order_type: str) -> float:
        spread = max(0.0, spread_bps)
        vol = max(0.0, min(1.0, volatility_score))
        latency = max(0.0, min(1.0, latency_risk))

        base = 0.93 - min(0.25, spread * 0.02) - vol * 0.22 - latency * 0.18
        if order_type == "LIMIT":
            base -= 0.10
        elif order_type == "POST_ONLY":
            base -= 0.18
        return max(0.05, min(0.99, base))
