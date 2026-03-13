from __future__ import annotations

from collections import deque
import numpy as np


class EdgeHealthMonitor:
    def __init__(self):
        self.history = {}

    def update(self, strategy: str, r_multiple: float):
        self.history.setdefault(strategy, deque(maxlen=100)).append(float(r_multiple))

    def metrics(self, strategy: str):
        xs = list(self.history.get(strategy, []))
        if not xs:
            return {
                "trade_count": 0,
                "expectancy": 0.0,
                "expectancy_recent": 0.0,
                "win_rate": 0.0,
                "win_rate_recent": 0.0,
                "profit_factor": 0.0,
                "drawdown_slope": 0.0,
                "max_drawdown": 0.0,
            }
        wins = [x for x in xs if x > 0]
        losses = [x for x in xs if x <= 0]
        pf = (sum(wins) / max(1e-9, abs(sum(losses)))) if losses else 9.99
        recent = np.array(xs[-20:])
        dd_series = np.cumsum(xs)
        running_peak = np.maximum.accumulate(dd_series)
        dd = dd_series - running_peak
        slope = float(dd[-1] - dd[0]) / max(1, len(dd) - 1)
        return {
            "trade_count": len(xs),
            "expectancy": float(np.mean(xs)),
            "expectancy_recent": float(np.mean(recent)),
            "win_rate": float(np.mean(np.array(xs) > 0)),
            "win_rate_recent": float(np.mean(recent > 0)),
            "profit_factor": float(pf),
            "drawdown_slope": slope,
            "max_drawdown": float(np.min(dd)),
        }

    def edge_decayed(
        self,
        strategy: str,
        min_trades: int = 20,
        dd_slope_threshold: float = -0.03,
        min_recent_expectancy: float = -0.05,
    ):
        xs = list(self.history.get(strategy, []))
        if len(xs) < min_trades:
            return False, {"reason": "insufficient_trades"}
        m = self.metrics(strategy)
        recent_underperforming = m["expectancy_recent"] <= min_recent_expectancy
        broad_weakness = m["expectancy"] < 0 and m["win_rate_recent"] < 0.45
        drawdown_accelerating = m["drawdown_slope"] < dd_slope_threshold and m["max_drawdown"] < -2.0
        decayed = recent_underperforming and (broad_weakness or drawdown_accelerating)
        return decayed, m
