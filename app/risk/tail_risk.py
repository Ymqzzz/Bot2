from __future__ import annotations

import statistics


def realized_returns(bars: list[dict]) -> list[float]:
    closes = [float(b["close"]) for b in bars]
    out = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        out.append((closes[i] - prev) / max(prev, 1e-9))
    return out


def var_es(returns: list[float], alpha: float = 0.99) -> tuple[float, float]:
    if not returns:
        return 0.0, 0.0
    xs = sorted(returns)
    idx = max(0, int((1 - alpha) * len(xs)) - 1)
    var = xs[idx]
    tail = [x for x in xs if x <= var]
    es = sum(tail) / max(1, len(tail))
    return var, es


def dislocation_score(bars: list[dict], spread_pctile: float) -> float:
    rs = realized_returns(bars[-80:])
    if not rs:
        return 0.0
    vol = statistics.pstdev(rs)
    jump = max(abs(x) for x in rs[-20:])
    spread_component = max(0.0, (spread_pctile - 70.0) / 30.0)
    return min(3.0, (vol * 400.0) + (jump * 800.0) + spread_component)
