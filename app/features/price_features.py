from __future__ import annotations

import statistics


def _ema(xs: list[float], period: int) -> float:
    if not xs:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    out = xs[0]
    for x in xs[1:]:
        out = alpha * x + (1 - alpha) * out
    return out


def _atr(bars: list[dict], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])
        pc = float(bars[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-period:] if len(trs) >= period else trs
    return float(sum(window) / max(1, len(window)))


def compute_price_features(bars: list[dict]) -> dict:
    closes = [float(b["close"]) for b in bars]
    if len(closes) < 30:
        return {"ema_fast": 0.0, "ema_slow": 0.0, "ema_slope": 0.0, "zscore": 0.0, "atr": 0.0}
    ema_fast = _ema(closes[-40:], 10)
    ema_slow = _ema(closes[-60:], 30)
    mean = statistics.fmean(closes[-50:])
    stdev = statistics.pstdev(closes[-50:]) or 1e-9
    zscore = (closes[-1] - mean) / stdev
    return {
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "ema_slope": ema_fast - ema_slow,
        "zscore": zscore,
        "atr": _atr(bars),
    }
