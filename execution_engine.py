from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List

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
    """Select an entry type balancing momentum intent and current market frictions."""
    is_breakout = "breakout" in strategy.lower()
    if is_breakout and breakout_mag > 0.35 and liquidity_factor > 0.55:
        return "STOP"
    if spread_pctile > 80 and not is_breakout:
        return "LIMIT"
    return "MARKET"


def _balanced_unit_clips(units: int, clip_count: int) -> List[int]:
    """Split signed units into near-even clips while preserving total size."""
    sign = -1 if units < 0 else 1
    abs_units = abs(units)
    base = abs_units // clip_count
    remainder = abs_units % clip_count
    clips = [base + (1 if i < remainder else 0) for i in range(clip_count)]
    return [sign * c for c in clips]


def clip_staging_plan(
    units: int,
    liquidity_factor: float,
    has_near_event: bool,
    clips_min: int = 2,
    clips_max: int = 4,
) -> List[int]:
    """Create a staged execution plan with bounded clip count and balanced clip sizes."""
    if abs(units) < 2 or liquidity_factor < 0.6 or has_near_event:
        return [int(units)]

    lower = max(1, int(clips_min))
    upper = max(lower, int(clips_max))
    clip_count = min(abs(units), upper)
    clip_count = max(lower, clip_count)

    return _balanced_unit_clips(int(units), clip_count)
