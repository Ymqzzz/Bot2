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
            return {"expectancy": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "drawdown_slope": 0.0}
        wins = [x for x in xs if x > 0]
        losses = [x for x in xs if x <= 0]
        pf = (sum(wins) / max(1e-9, abs(sum(losses)))) if losses else 9.99
        dd_series = np.cumsum(xs)
        running_peak = np.maximum.accumulate(dd_series)
        dd = dd_series - running_peak
        slope = float(dd[-1] - dd[0]) / max(1, len(dd) - 1)
        return {"expectancy": float(np.mean(xs)), "win_rate": float(np.mean(np.array(xs) > 0)), "profit_factor": float(pf), "drawdown_slope": slope}

    def edge_decayed(self, strategy: str, min_trades: int = 20, dd_slope_threshold: float = -0.03):
        xs = list(self.history.get(strategy, []))
        if len(xs) < min_trades:
            return False, {"reason": "insufficient_trades"}
        m = self.metrics(strategy)
        decayed = m["expectancy"] < 0 and m["drawdown_slope"] < dd_slope_threshold
        return decayed, m
