from __future__ import annotations

import numpy as np
import pandas as pd


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
