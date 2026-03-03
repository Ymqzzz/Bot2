from __future__ import annotations

from collections import defaultdict, deque
import numpy as np


class ExecutionStats:
    def __init__(self, maxlen: int = 200):
        self.slippage = defaultdict(lambda: deque(maxlen=maxlen))
        self.spread = defaultdict(lambda: deque(maxlen=maxlen))

    def record_fill(self, instrument: str, spread: float, expected_price: float, filled_price: float):
        slip = abs(filled_price - expected_price)
        self.slippage[instrument].append(float(slip))
        self.spread[instrument].append(float(spread))

    def summary(self, instrument: str):
        sl = list(self.slippage[instrument])
        sp = list(self.spread[instrument])
        if not sl or not sp:
            return {"slippage_avg": 0.0, "slippage_p95": 0.0, "spread_p95": 0.0, "spread_pctile": 50.0}
        return {
            "slippage_avg": float(np.mean(sl)),
            "slippage_p95": float(np.percentile(sl, 95)),
            "spread_p95": float(np.percentile(sp, 95)),
            "spread_pctile": float((np.sum(np.array(sp) <= sp[-1]) / len(sp)) * 100.0),
        }


def choose_entry_type(strategy: str, breakout_mag: float, liquidity_factor: float, spread_pctile: float) -> str:
    is_breakout = "breakout" in strategy.lower()
    if is_breakout and breakout_mag > 0.35 and liquidity_factor > 0.55:
        return "STOP"
    if spread_pctile > 80 and not is_breakout:
        return "LIMIT"
    return "MARKET"


def clip_staging_plan(units: int, liquidity_factor: float, has_near_event: bool, clips_min: int = 2, clips_max: int = 4):
    if abs(units) < 2 or liquidity_factor < 0.6 or has_near_event:
        return [int(units)]
    clips = max(clips_min, min(clips_max, abs(units) // max(1, abs(units) // clips_max)))
    each = int(units / clips)
    plan = [each] * clips
    plan[-1] += units - sum(plan)
    return plan
