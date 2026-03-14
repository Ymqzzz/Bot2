from __future__ import annotations

from collections import deque
import math
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
                "win_rate_posterior_mean": 0.5,
                "prob_positive_expectancy": 0.5,
                "profit_factor": 0.0,
                "drawdown_slope": 0.0,
                "max_drawdown": 0.0,
            }
        wins = [x for x in xs if x > 0]
        losses = [x for x in xs if x <= 0]
        pf = (sum(wins) / max(1e-9, abs(sum(losses)))) if losses else 9.99
        recent = np.array(xs[-20:])

        arr = np.array(xs)
        dd_series = np.cumsum(arr)
        running_peak = np.maximum.accumulate(dd_series)
        dd = dd_series - running_peak
        slope = float(dd[-1] - dd[0]) / max(1, len(dd) - 1)

        # Beta-binomial posterior for win-rate with weakly informative prior.
        alpha0, beta0 = 2.0, 2.0
        alpha_post = alpha0 + len(wins)
        beta_post = beta0 + len(losses)
        posterior_wr = alpha_post / (alpha_post + beta_post)

        # Approximate posterior probability of positive expectancy using normal model.
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if len(arr) > 1 else max(0.05, abs(mean))
        se = max(1e-6, std / math.sqrt(len(arr)))
        z = mean / se
        prob_positive_expectancy = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

        return {
            "trade_count": len(xs),
            "expectancy": mean,
            "expectancy_recent": float(np.mean(recent)),
            "win_rate": float(np.mean(arr > 0)),
            "win_rate_recent": float(np.mean(recent > 0)),
            "win_rate_posterior_mean": float(posterior_wr),
            "prob_positive_expectancy": float(prob_positive_expectancy),
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
        min_prob_positive_expectancy: float = 0.35,
    ):
        xs = list(self.history.get(strategy, []))
        if len(xs) < min_trades:
            return False, {"reason": "insufficient_trades"}
        m = self.metrics(strategy)
        recent_underperforming = m["expectancy_recent"] <= min_recent_expectancy
        broad_weakness = m["expectancy"] < 0 and m["win_rate_recent"] < 0.45
        posterior_weakness = m["prob_positive_expectancy"] < min_prob_positive_expectancy
        drawdown_accelerating = m["drawdown_slope"] < dd_slope_threshold and m["max_drawdown"] < -2.0
        decayed = (recent_underperforming and (broad_weakness or drawdown_accelerating)) or posterior_weakness
        return decayed, m
