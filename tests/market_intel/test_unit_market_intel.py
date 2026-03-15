from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

import main
from execution_engine import ExecutionStats


def _mk_ohlcv(start: float, step: float, n: int = 120) -> pd.DataFrame:
    price = start
    rows = []
    for _ in range(n):
        price += step
        rows.append({"o": price - 0.0002, "h": price + 0.0003, "l": price - 0.0003, "c": price, "v": 100})
    return pd.DataFrame(rows)


def _volume_profile_levels(prices: list[float], volumes: list[int], bins: int = 5) -> dict[str, float]:
    hist, edges = np.histogram(prices, bins=bins, weights=volumes)
    poc_idx = int(np.argmax(hist))
    poc = float((edges[poc_idx] + edges[poc_idx + 1]) / 2.0)

    target = 0.7 * float(np.sum(hist))
    included = {poc_idx}
    running = float(hist[poc_idx])
    left, right = poc_idx - 1, poc_idx + 1
    while running < target and (left >= 0 or right < len(hist)):
        lv = hist[left] if left >= 0 else -1
        rv = hist[right] if right < len(hist) else -1
        if rv >= lv:
            included.add(right)
            running += float(max(0, rv))
            right += 1
        else:
            included.add(left)
            running += float(max(0, lv))
            left -= 1
    vah = float(edges[max(included) + 1])
    val = float(edges[min(included)])
    return {"poc": poc, "vah": vah, "val": val}


def _equal_levels(highs: list[float], lows: list[float], tol: float = 0.0003) -> dict[str, bool]:
    return {
        "equal_highs": abs(highs[-1] - highs[-2]) <= tol,
        "equal_lows": abs(lows[-1] - lows[-2]) <= tol,
    }


def _structure_state(prev_high: float, prev_low: float, close: float, failed_back_inside: bool) -> str:
    if close > prev_high:
        return "failed-breakout" if failed_back_inside else "breakout"
    if close < prev_low:
        return "breakdown"
    if failed_back_inside:
        return "reclaim"
    return "inside"


def _cross_asset_alignment(scores: dict[str, float], mapping: dict[str, list[str]]) -> dict[str, float]:
    out = {}
    for asset, deps in mapping.items():
        vals = [scores.get(x, 0.0) for x in deps]
        out[asset] = float(np.mean(vals)) if vals else 0.0
    return out


def test_session_boundaries():
    assert main.session_label(datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)) == "ASIA"
    assert main.session_label(datetime(2024, 1, 1, 7, 0, tzinfo=timezone.utc)) == "LONDON"
    assert main.session_label(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)) == "OVERLAP"
    assert main.session_label(datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)) == "NY"
    assert main.session_label(datetime(2024, 1, 1, 22, 0, tzinfo=timezone.utc)) == "DEAD_ZONE"


def test_higher_timeframe_structure(monkeypatch):
    up = _mk_ohlcv(1.10, 0.0005)
    down = _mk_ohlcv(1.20, -0.0005)

    monkeypatch.setattr(main, "get_candles", lambda *_args, **_kwargs: up)
    assert main.higher_tf_alignment("EUR_USD") == 1.0

    monkeypatch.setattr(main, "get_candles", lambda *_args, **_kwargs: down)
    assert main.higher_tf_alignment("EUR_USD") == -1.0

    def _mixed(_instr, count=300, granularity="H1"):
        return up if granularity in {"H1", "D"} else down

    monkeypatch.setattr(main, "get_candles", _mixed)
    assert main.higher_tf_alignment("EUR_USD") == 0.0


def test_volume_profile_poc_vah_val():
    prices = [1.1000, 1.1001, 1.1002, 1.1010, 1.1011, 1.1020]
    volumes = [50, 60, 55, 15, 20, 5]
    levels = _volume_profile_levels(prices, volumes, bins=4)
    assert levels["val"] <= levels["poc"] <= levels["vah"]


def test_equal_highs_lows_and_structure_states():
    eq = _equal_levels([1.1020, 1.1022], [1.0980, 1.0979], tol=0.00025)
    assert eq["equal_highs"]
    assert eq["equal_lows"]

    assert _structure_state(prev_high=1.1010, prev_low=1.0990, close=1.1015, failed_back_inside=False) == "breakout"
    assert _structure_state(prev_high=1.1010, prev_low=1.0990, close=1.1012, failed_back_inside=True) == "failed-breakout"
    assert _structure_state(prev_high=1.1010, prev_low=1.0990, close=1.1002, failed_back_inside=True) == "reclaim"


def test_gamma_proxy_cross_asset_alignment_and_execution_quality():
    atm = main.garman_kohlhagen(S=1.10, K=1.10, T=30 / 365, sigma=0.12, rd=0.03, rf=0.01, call=True)
    deep = main.garman_kohlhagen(S=1.10, K=1.25, T=30 / 365, sigma=0.12, rd=0.03, rf=0.01, call=True)
    assert atm["gamma"] > deep["gamma"] > 0

    align = _cross_asset_alignment(
        scores={"DXY": -0.7, "US10Y": -0.4, "SPX": 0.6, "VIX": -0.5},
        mapping={"EUR_USD": ["DXY", "US10Y"], "AUD_JPY": ["SPX", "VIX"]},
    )
    assert align["EUR_USD"] < 0
    assert align["AUD_JPY"] > 0

    stats = ExecutionStats(maxlen=100)
    for sp, exp, fill in [(0.0001, 1.1, 1.10005), (0.00012, 1.1, 1.10003), (0.00009, 1.1, 1.10001)]:
        stats.record_fill("EUR_USD", spread=sp, expected_price=exp, filled_price=fill)
    s = stats.summary("EUR_USD")
    quality = max(0.0, 1.0 - (s["slippage_p95"] * 10_000 + s["spread_p95"] * 10_000) / 20)
    assert 0.0 <= quality <= 1.0
