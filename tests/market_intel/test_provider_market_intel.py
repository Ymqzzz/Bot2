from __future__ import annotations

import time
from collections import defaultdict

import main


def _cross_asset_fallback(asset: str, provider_map: dict[str, str], default_map: dict[str, str]) -> str:
    return provider_map.get(asset) or default_map.get(asset) or "GLOBAL"


def test_oanda_candle_normalization(monkeypatch):
    payload = {
        "candles": [
            {
                "complete": True,
                "time": "2024-01-01T00:00:00Z",
                "mid": {"o": "1.1000", "h": "1.1010", "l": "1.0990", "c": "1.1005"},
                "volume": 12,
            },
            {
                "complete": False,
                "time": "2024-01-01T00:05:00Z",
                "mid": {"o": "1.1005", "h": "1.1015", "l": "1.1000", "c": "1.1008"},
                "volume": 7,
            },
        ]
    }
    monkeypatch.setattr(main, "safe_get", lambda *_args, **_kwargs: payload)

    df = main.get_candles("EUR_USD", count=2, granularity="M5")

    assert len(df) == 1
    assert list(df.columns) == ["time", "o", "h", "l", "c", "v"]
    assert df.iloc[0]["v"] == 12


def test_stale_handling_and_missing_provider_fallback(monkeypatch):
    monkeypatch.setattr(main, "safe_get", lambda *_args, **_kwargs: None)
    assert main.get_candles("EUR_USD", count=2, granularity="M5") is None

    now = time.time()
    monkeypatch.setattr(main, "spread_cache", {"EUR_USD": 0.0002})
    monkeypatch.setattr(main, "spread_history", defaultdict(list, {"EUR_USD": [(now - 9, 0.0002), (now - 8, 0.0002)]}))
    blocked, info = main.spread_liquidity_guard("EUR_USD")
    assert blocked
    assert info["stale"] is True


def test_tick_synth_behavior_and_per_asset_cross_asset_fallback(monkeypatch):
    monkeypatch.setattr(main, "spread_cache", {"EUR_USD": 0.0001})
    monkeypatch.setattr(main, "spread_history", defaultdict(list, {"EUR_USD": []}))
    assert main.liquidity_factor("EUR_USD") == 0.5

    provider_map = {"EUR_USD": "EU_PROVIDER"}
    default_map = {"AUD_JPY": "RISK_PROVIDER"}
    assert _cross_asset_fallback("EUR_USD", provider_map, default_map) == "EU_PROVIDER"
    assert _cross_asset_fallback("AUD_JPY", provider_map, default_map) == "RISK_PROVIDER"
    assert _cross_asset_fallback("USD_CHF", provider_map, default_map) == "GLOBAL"
