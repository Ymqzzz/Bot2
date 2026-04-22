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


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses += -delta
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss <= 1e-12:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(closes: list[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> tuple[float, float, float]:
    if len(closes) < slow_period + signal_period:
        return 0.0, 0.0, 0.0
    ema_fast_series: list[float] = []
    ema_slow_series: list[float] = []
    alpha_fast = 2.0 / (fast_period + 1.0)
    alpha_slow = 2.0 / (slow_period + 1.0)
    ef = closes[0]
    es = closes[0]
    for c in closes:
        ef = alpha_fast * c + (1.0 - alpha_fast) * ef
        es = alpha_slow * c + (1.0 - alpha_slow) * es
        ema_fast_series.append(ef)
        ema_slow_series.append(es)
    macd_series = [f - s for f, s in zip(ema_fast_series, ema_slow_series)]
    signal = _ema(macd_series[-(signal_period * 3) :], signal_period)
    macd = macd_series[-1]
    hist = macd - signal
    return macd, signal, hist


def _bollinger_position(closes: list[float], period: int = 20, stdev_mult: float = 2.0) -> tuple[float, float]:
    if len(closes) < period:
        return 0.5, 0.0
    window = closes[-period:]
    mean = statistics.fmean(window)
    stdev = statistics.pstdev(window)
    upper = mean + stdev_mult * stdev
    lower = mean - stdev_mult * stdev
    width = max(upper - lower, 1e-9)
    pos = _safe_div(closes[-1] - lower, width, default=0.5)
    bandwidth = _safe_div(width, max(mean, 1e-9))
    return max(0.0, min(1.0, pos)), max(0.0, bandwidth)


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
            "directional_efficiency": 0.0,
            "range_compression": 0.0,
            "wick_rejection_bias": 0.0,
            "price_action_trend_score": 0.0,
            "price_action_mean_revert_score": 0.0,
            "price_action_breakout_score": 0.0,
            "price_action_confidence": 0.0,
            "price_action_id": 0.0,
            "trend_alignment": 0.0,
            "trend_consistency": 0.0,
            "reversion_pressure": 0.0,
            "breakout_pressure": 0.0,
            "range_compression": 0.0,
            "impulse_strength": 0.0,
            "pullback_quality": 0.0,
            "rsi_14": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_hist": 0.0,
            "bb_pos": 0.5,
            "bb_bandwidth": 0.0,
            "algo_trend_strength": 0.0,
            "algo_mean_revert_strength": 0.0,
            "algo_breakout_strength": 0.0,
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
    abs_path = sum(abs(closes[i] - closes[i - 1]) for i in range(max(1, len(closes) - 20), len(closes)))
    directional_efficiency = min(1.0, abs(closes[-1] - closes[-20]) / max(abs_path, 1e-9)) if len(closes) > 20 else 0.0

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
    bar_ranges = [max(1e-9, h - l) for h, l in zip(highs[-30:], lows[-30:])]
    recent_range = statistics.fmean(bar_ranges[-8:])
    baseline_range = statistics.fmean(bar_ranges)
    range_compression = max(0.0, min(1.0, 1.0 - _safe_div(recent_range, baseline_range, default=1.0)))
    upper_wick = max(0.0, current_high - max(current_close, float(bars[-1]["open"])))
    lower_wick = max(0.0, min(current_close, float(bars[-1]["open"])) - current_low)
    wick_rejection_bias = max(-1.0, min(1.0, _safe_div(lower_wick - upper_wick, current_range, default=0.0)))

    trend_strength = min(1.0, abs(ema_fast - ema_slow) / max(2.5 * atr, 1e-9))
    vol_penalty = min(1.0, realized_vol * 100.0)
    chop_regime = max(0.0, min(1.0, (1.0 - trend_strength) * 0.7 + vol_penalty * 0.3))
    trend_regime = max(0.0, min(1.0, 1.0 - chop_regime))
    confluence = max(0.0, min(1.0, 0.5 * trend_regime + 0.3 * (1.0 - min(1.0, abs(zscore) / 4.0)) + 0.2 * (1.0 - vol_penalty)))
    confidence = max(0.0, min(1.0, 0.35 + 0.4 * confluence + 0.25 * trend_regime))
    impulse = min(1.0, abs(momentum) / 3.0)
    mean_revert_tension = min(1.0, abs(zscore) / 2.5)
    price_action_trend_score = max(0.0, min(1.0, 0.45 * directional_efficiency + 0.35 * trend_strength + 0.20 * (1.0 - range_compression)))
    price_action_mean_revert_score = max(
        0.0,
        min(
            1.0,
            0.45 * mean_revert_tension
            + 0.30 * range_compression
            + 0.25 * (1.0 - directional_efficiency),
        ),
    )
    price_action_breakout_score = max(
        0.0,
        min(
            1.0,
            0.35 * bos
            + 0.25 * impulse
            + 0.20 * directional_efficiency
            + 0.20 * (1.0 - min(1.0, abs(zscore) / 5.0)),
        ),
    )
    pa_scores = {
        1.0: price_action_trend_score,
        2.0: price_action_mean_revert_score,
        3.0: price_action_breakout_score,
    }
    best_id, best_score = max(pa_scores.items(), key=lambda x: x[1])
    second_score = sorted(pa_scores.values())[-2]
    price_action_confidence = max(0.0, min(1.0, 0.55 + (best_score - second_score)))
    trend_alignment = max(-1.0, min(1.0, _safe_div(ema_fast - ema_slow, max(2.0 * atr, 1e-9))))
    trend_consistency = max(0.0, min(1.0, (abs(ret_3) + abs(ret_12)) * 6.0))
    reversion_pressure = max(0.0, min(1.0, abs(zscore) / 3.0 * (0.6 + 0.4 * chop_regime)))
    breakout_pressure = max(0.0, min(1.0, abs(ret_1) * 120.0 + 0.45 * trend_regime + 0.2 * bos))
    range_compression = max(0.0, min(1.0, _safe_div(atr, current_close) * 250.0))
    impulse_strength = max(0.0, min(1.0, _safe_div(abs(momentum), 2.5) * (0.7 + 0.3 * trend_regime)))
    pullback_quality = max(0.0, min(1.0, trend_regime * (1.0 - min(1.0, abs(zscore) / 2.2))))
    rsi_14 = _rsi(closes, period=14)
    macd, macd_signal, macd_hist = _macd(closes)
    bb_pos, bb_bandwidth = _bollinger_position(closes, period=20, stdev_mult=2.0)
    rsi_centered = abs(rsi_14 - 50.0) / 50.0
    algo_trend_strength = max(
        0.0,
        min(
            1.0,
            0.45 * trend_strength + 0.25 * directional_efficiency + 0.15 * min(1.0, abs(macd_hist) / max(atr, 1e-9)) + 0.15 * rsi_centered,
        ),
    )
    algo_mean_revert_strength = max(
        0.0,
        min(
            1.0,
            0.40 * min(1.0, abs(zscore) / 3.0) + 0.30 * (1.0 - directional_efficiency) + 0.20 * (1.0 - trend_strength) + 0.10 * abs(bb_pos - 0.5) * 2.0,
        ),
    )
    algo_breakout_strength = max(
        0.0,
        min(
            1.0,
            0.35 * breakout_pressure + 0.25 * min(1.0, bb_bandwidth * 30.0) + 0.20 * bos + 0.20 * min(1.0, abs(macd_hist) / max(atr, 1e-9)),
        ),
    )

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
        "directional_efficiency": directional_efficiency,
        "range_compression": range_compression,
        "wick_rejection_bias": wick_rejection_bias,
        "price_action_trend_score": price_action_trend_score,
        "price_action_mean_revert_score": price_action_mean_revert_score,
        "price_action_breakout_score": price_action_breakout_score,
        "price_action_confidence": price_action_confidence,
        "price_action_id": best_id,
        "trend_alignment": trend_alignment,
        "trend_consistency": trend_consistency,
        "reversion_pressure": reversion_pressure,
        "breakout_pressure": breakout_pressure,
        "range_compression": range_compression,
        "impulse_strength": impulse_strength,
        "pullback_quality": pullback_quality,
        "rsi_14": rsi_14,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "bb_pos": bb_pos,
        "bb_bandwidth": bb_bandwidth,
        "algo_trend_strength": algo_trend_strength,
        "algo_mean_revert_strength": algo_mean_revert_strength,
        "algo_breakout_strength": algo_breakout_strength,
    }
