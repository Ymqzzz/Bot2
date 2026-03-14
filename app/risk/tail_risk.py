from __future__ import annotations

import math
import statistics


def realized_returns(bars: list[dict]) -> list[float]:
    closes = [float(b["close"]) for b in bars if "close" in b]
    out = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        curr = closes[i]
        if prev <= 0.0 or curr <= 0.0:
            continue
        out.append(math.log(curr / prev))
    return out


def var_es(returns: list[float], alpha: float = 0.99) -> tuple[float, float]:
    if not returns:
        return 0.0, 0.0
    alpha = min(0.999, max(0.80, float(alpha)))
    xs = sorted(returns)
    # Empirical quantile with a conservative lower interpolation.
    q = max(0.0, (1 - alpha) * (len(xs) - 1))
    lo = int(math.floor(q))
    hi = int(math.ceil(q))
    if lo == hi:
        var = xs[lo]
    else:
        w = q - lo
        var = xs[lo] * (1.0 - w) + xs[hi] * w
    tail_count = max(1, int(math.ceil((1 - alpha) * len(xs))))
    tail = xs[:tail_count]
    es = sum(tail) / max(1, len(tail))
    return var, es


def dislocation_score(bars: list[dict], spread_pctile: float) -> float:
    rs = realized_returns(bars[-80:])
    if len(rs) < 10:
        return 0.0
    vol = statistics.pstdev(rs)
    median_abs_move = statistics.median(abs(x) for x in rs) or 1e-6
    recent_window = rs[-20:]
    jump = max(abs(x) for x in recent_window)
    recent_drift = abs(sum(recent_window) / len(recent_window))
    spread_component = max(0.0, (spread_pctile - 70.0) / 30.0)
    jump_component = max(0.0, (jump / median_abs_move) - 1.0)
    drift_scale = max(vol, median_abs_move, 1e-6)
    drift_component = max(0.0, (recent_drift / drift_scale) - 1.0)
    score = (vol * 350.0) + (jump_component * 0.45) + (drift_component * 0.2) + spread_component
    return min(3.0, max(0.0, score))
