from __future__ import annotations

import pandas as pd


def compute_regime_features(snapshot: dict | None, bars: pd.DataFrame | None) -> dict[str, float]:
    snapshot = snapshot or {}
    bars = bars if bars is not None else pd.DataFrame()
    close = bars.get("close") if not bars.empty and "close" in bars else pd.Series([1.0, 1.0])
    trend = float(abs(close.iloc[-1] - close.iloc[0]) / max(abs(close.iloc[-1]), 1e-8))
    return {
        "trend_strength": max(0.0, min(1.0, trend)),
        "rotation": float(snapshot.get("rotation", 0.0) or 0.0),
        "compression": float(snapshot.get("compression", 0.0) or 0.0),
        "expansion": float(snapshot.get("velocity", 0.0) or 0.0),
        "event_chaos": float(snapshot.get("event_chaos", snapshot.get("spread_shock", 0.0)) or 0.0),
    }
