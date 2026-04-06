from __future__ import annotations

import math
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


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if abs(denominator) < 1e-12:
        return default
    return numerator / denominator


def _linreg_slope(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    n = len(xs)
    x_mean = (n - 1) / 2.0
    y_mean = statistics.fmean(xs)
    cov = 0.0
    var = 0.0
    for i, y in enumerate(xs):
        dx = i - x_mean
        cov += dx * (y - y_mean)
        var += dx * dx
    return _safe_div(cov, var)


def _rolling_returns(closes: list[float], lookback: int) -> float:
    if len(closes) <= lookback:
        return 0.0
    return _safe_div(closes[-1] - closes[-1 - lookback], closes[-1 - lookback])


def _realized_vol(closes: list[float], window: int = 20) -> float:
    if len(closes) < 3:
        return 0.0
    rets = []
    for i in range(max(1, len(closes) - window), len(closes)):
        prev = closes[i - 1]
        if prev <= 0:
            continue
        rets.append(math.log(closes[i] / prev))
    if len(rets) < 2:
        return 0.0
    return statistics.pstdev(rets) * math.sqrt(len(rets))


def _vwap_distance(bars: list[dict], window: int = 30) -> float:
    sample = bars[-window:] if len(bars) > window else bars
    weighted_px = 0.0
    weighted_vol = 0.0
    for idx, bar in enumerate(sample):
        typical = (float(bar["high"]) + float(bar["low"]) + float(bar["close"])) / 3.0
        synthetic_vol = idx + 1
        weighted_px += typical * synthetic_vol
        weighted_vol += synthetic_vol
    if weighted_vol <= 0:
        return 0.0
    vwap = weighted_px / weighted_vol
    close = float(sample[-1]["close"])
    return _safe_div(close - vwap, vwap)


def compute_price_features(bars: list[dict]) -> dict:
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    if len(closes) < 30:
        return {
            "ema_fast": 0.0,
            "ema_slow": 0.0,
            "ema_slope": 0.0,
            "zscore": 0.0,
            "atr": 0.0,
            "ret_1": 0.0,
            "ret_3": 0.0,
            "ret_12": 0.0,
            "realized_vol": 0.0,
            "trend_slope": 0.0,
            "momentum": 0.0,
            "vwap_distance": 0.0,
            "daily_range_pos": 0.5,
            "prev_day_hilo_proximity": 0.0,
            "liquidity_sweep": 0.0,
            "bos": 0.0,
            "trend_regime": 0.5,
            "chop_regime": 0.5,
            "confluence": 0.0,
            "confidence": 0.0,
            "trend_alignment": 0.0,
            "trend_consistency": 0.0,
            "reversion_pressure": 0.0,
            "breakout_pressure": 0.0,
            "range_compression": 0.0,
            "impulse_strength": 0.0,
            "pullback_quality": 0.0,
        }
    ema_fast = _ema(closes[-40:], 10)
    ema_slow = _ema(closes[-60:], 30)
    mean = statistics.fmean(closes[-50:])
    stdev = statistics.pstdev(closes[-50:]) or 1e-9
    zscore = (closes[-1] - mean) / stdev
    atr = _atr(bars)
    ret_1 = _rolling_returns(closes, 1)
    ret_3 = _rolling_returns(closes, 3)
    ret_12 = _rolling_returns(closes, 12)
    realized_vol = _realized_vol(closes, window=20)
    trend_slope = _linreg_slope(closes[-20:])
    momentum = _safe_div(closes[-1] - closes[-11], max(atr, 1e-9)) if len(closes) > 11 else 0.0

    current_high = highs[-1]
    current_low = lows[-1]
    current_close = closes[-1]
    current_range = max(1e-9, current_high - current_low)
    daily_range_pos = _safe_div(current_close - current_low, current_range, default=0.5)
    prior_high = max(highs[-25:-1]) if len(highs) > 25 else max(highs[:-1])
    prior_low = min(lows[-25:-1]) if len(lows) > 25 else min(lows[:-1])
    proximity_hi = abs(current_close - prior_high)
    proximity_lo = abs(current_close - prior_low)
    prev_day_hilo_proximity = _safe_div(min(proximity_hi, proximity_lo), max(atr, 1e-9))
    liquidity_sweep = 1.0 if (current_high > prior_high and current_close < prior_high) or (current_low < prior_low and current_close > prior_low) else 0.0
    bos = 1.0 if (current_close > prior_high or current_close < prior_low) else 0.0

    trend_strength = min(1.0, abs(ema_fast - ema_slow) / max(2.5 * atr, 1e-9))
    vol_penalty = min(1.0, realized_vol * 100.0)
    chop_regime = max(0.0, min(1.0, (1.0 - trend_strength) * 0.7 + vol_penalty * 0.3))
    trend_regime = max(0.0, min(1.0, 1.0 - chop_regime))
    confluence = max(0.0, min(1.0, 0.5 * trend_regime + 0.3 * (1.0 - min(1.0, abs(zscore) / 4.0)) + 0.2 * (1.0 - vol_penalty)))
    confidence = max(0.0, min(1.0, 0.35 + 0.4 * confluence + 0.25 * trend_regime))
    trend_alignment = max(-1.0, min(1.0, _safe_div(ema_fast - ema_slow, max(2.0 * atr, 1e-9))))
    trend_consistency = max(0.0, min(1.0, (abs(ret_3) + abs(ret_12)) * 6.0))
    reversion_pressure = max(0.0, min(1.0, abs(zscore) / 3.0 * (0.6 + 0.4 * chop_regime)))
    breakout_pressure = max(0.0, min(1.0, abs(ret_1) * 120.0 + 0.45 * trend_regime + 0.2 * bos))
    range_compression = max(0.0, min(1.0, _safe_div(atr, current_close) * 250.0))
    impulse_strength = max(0.0, min(1.0, _safe_div(abs(momentum), 2.5) * (0.7 + 0.3 * trend_regime)))
    pullback_quality = max(0.0, min(1.0, trend_regime * (1.0 - min(1.0, abs(zscore) / 2.2))))

    return {
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "ema_slope": ema_fast - ema_slow,
        "zscore": zscore,
        "atr": atr,
        "ret_1": ret_1,
        "ret_3": ret_3,
        "ret_12": ret_12,
        "realized_vol": realized_vol,
        "trend_slope": trend_slope,
        "momentum": momentum,
        "vwap_distance": _vwap_distance(bars, window=30),
        "daily_range_pos": daily_range_pos,
        "prev_day_hilo_proximity": prev_day_hilo_proximity,
        "liquidity_sweep": liquidity_sweep,
        "bos": bos,
        "trend_regime": trend_regime,
        "chop_regime": chop_regime,
        "confluence": confluence,
        "confidence": confidence,
        "trend_alignment": trend_alignment,
        "trend_consistency": trend_consistency,
        "reversion_pressure": reversion_pressure,
        "breakout_pressure": breakout_pressure,
        "range_compression": range_compression,
        "impulse_strength": impulse_strength,
        "pullback_quality": pullback_quality,
    }
