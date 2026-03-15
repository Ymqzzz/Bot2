from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def _norm(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def extract_regime_features(market_intel_snapshot: dict[str, Any] | None, recent_bars: pd.DataFrame | None) -> dict[str, float]:
    snapshot = market_intel_snapshot or {}
    if recent_bars is None or recent_bars.empty:
        return {k: 0.0 for k in [
            "trend_strength_score", "rotation_score", "compression_score", "expansion_score", "sweep_tendency_score",
            "event_chaos_score", "dead_zone_score", "directional_persistence_score", "range_efficiency_score",
            "rv_expansion_factor", "value_area_rotation_score", "structure_rejection_density", "intraday_impulse_quality_score",
        ]}

    close = recent_bars["close"].astype(float)
    high = recent_bars["high"].astype(float)
    low = recent_bars["low"].astype(float)
    ret = close.pct_change().fillna(0.0)

    drift = abs(close.iloc[-1] - close.iloc[max(0, len(close) - 30)])
    path = float(np.abs(np.diff(close.tail(30))).sum() + 1e-9)
    directional_persistence = _norm(drift / path)

    vol_short = ret.tail(20).std()
    vol_long = ret.tail(80).std() if len(ret) >= 80 else ret.std()
    rv_expansion = _norm((vol_short / (vol_long + 1e-9)) / 2.0)

    rolling_range = (high - low).tail(20)
    median_range = float((high - low).tail(80).median() if len(high) >= 80 else (high - low).median())
    compression = _norm(1.0 - (float(rolling_range.mean()) / (median_range + 1e-9)))
    expansion = _norm((float(rolling_range.mean()) / (median_range + 1e-9)) - 1.0)

    ma = close.rolling(20).mean()
    dist_to_ma = ((close - ma) / (close.rolling(20).std() + 1e-9)).fillna(0.0)
    rotation = _norm(1.0 - min(1.0, abs(float(dist_to_ma.tail(10).mean()))))

    wick = ((high - close).abs() + (close - low).abs()) / ((high - low).abs() + 1e-9)
    structure_rejection_density = _norm(float((wick.tail(30) > 0.65).mean()))

    false_breaks = ((high.diff() > 0) & (close.diff() < 0)) | ((low.diff() < 0) & (close.diff() > 0))
    sweep_tendency = _norm(float(false_breaks.tail(30).mean()) * 2)

    range_efficiency = _norm(1.0 - directional_persistence)
    value_area_rotation = rotation
    impulse_quality = _norm((directional_persistence * 0.6) + (rv_expansion * 0.4))

    spread_shock = float(snapshot.get("spread_shock", 0.0) or 0.0)
    micro_noise = float(snapshot.get("micro_noise", 0.0) or 0.0)
    event_chaos = _norm((spread_shock * 0.6) + (micro_noise * 0.4))

    dead_zone = _norm((1.0 - rv_expansion) * 0.5 + (1.0 - impulse_quality) * 0.5)

    trend_strength = _norm((directional_persistence * 0.5) + (expansion * 0.3) + (impulse_quality * 0.2))

    return {
        "trend_strength_score": trend_strength,
        "rotation_score": rotation,
        "compression_score": compression,
        "expansion_score": expansion,
        "sweep_tendency_score": sweep_tendency,
        "event_chaos_score": event_chaos,
        "dead_zone_score": dead_zone,
        "directional_persistence_score": directional_persistence,
        "range_efficiency_score": range_efficiency,
        "rv_expansion_factor": rv_expansion,
        "value_area_rotation_score": value_area_rotation,
        "structure_rejection_density": structure_rejection_density,
        "intraday_impulse_quality_score": impulse_quality,
def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def extract_regime_features(recent_bars: pd.DataFrame, market_intel_snapshot: dict | None = None) -> dict[str, float]:
    market_intel_snapshot = market_intel_snapshot or {}
    if recent_bars is None or len(recent_bars) < 20:
        return {k: 0.0 for k in [
            "trend_strength_score", "rotation_score", "compression_score", "expansion_score", "sweep_tendency_score",
            "event_chaos_score", "dead_zone_score", "directional_persistence_score", "range_efficiency_score",
            "realized_vol_expansion_factor", "value_area_rotation_score", "structure_rejection_density", "intraday_impulse_quality_score",
        ]}
    close = recent_bars["close"].astype(float)
    high = recent_bars["high"].astype(float)
    low = recent_bars["low"].astype(float)
    ret = close.pct_change().dropna()
    abs_ret = ret.abs()
    sign = np.sign(ret)

    trend = _clamp01(abs((close.iloc[-1] - close.iloc[-20]) / max(close.iloc[-20], 1e-9)) * 12)
    persistence = _clamp01(float((sign.tail(15).diff().fillna(0) == 0).mean()))
    compression = _clamp01(1.0 - float((high.tail(20).max() - low.tail(20).min()) / max(close.tail(20).mean() * 0.01, 1e-9)))
    vol_fast = float(abs_ret.tail(12).mean())
    vol_slow = float(abs_ret.tail(60).mean() if len(abs_ret) >= 60 else abs_ret.mean())
    expansion = _clamp01((vol_fast / max(vol_slow, 1e-9)) - 0.75)
    rotation = _clamp01(1.0 - trend + float((sign.tail(20).rolling(2).sum() == 0).mean()) * 0.5)
    wick = ((high - close).abs() + (close - low).abs()) / ((high - low).replace(0, np.nan))
    rejection_density = _clamp01(float(wick.tail(20).fillna(0).mean()))
    sweep = _clamp01(rejection_density * (1.0 - persistence) * 1.25)
    dead_zone = _clamp01((1.0 - expansion) * (1.0 - trend) * (1.0 - vol_fast / max(0.0005, vol_slow + 1e-6)))
    chaos = _clamp01(float(market_intel_snapshot.get("spread_z", 0.0)) / 3.0 + float(market_intel_snapshot.get("event_risk", 0.0)))
    range_eff = _clamp01((high.tail(20).max() - low.tail(20).min()) / max(abs(close.iloc[-1] - close.iloc[-20]), 1e-9) / 20)
    value_rot = _clamp01(rotation * (1 - expansion) + rejection_density * 0.3)
    impulse = _clamp01(trend * expansion)

    return {
        "trend_strength_score": trend,
        "rotation_score": rotation,
        "compression_score": compression,
        "expansion_score": expansion,
        "sweep_tendency_score": sweep,
        "event_chaos_score": chaos,
        "dead_zone_score": dead_zone,
        "directional_persistence_score": persistence,
        "range_efficiency_score": range_eff,
        "realized_vol_expansion_factor": _clamp01(expansion * 1.2),
        "value_area_rotation_score": value_rot,
        "structure_rejection_density": rejection_density,
        "intraday_impulse_quality_score": impulse,
    }
