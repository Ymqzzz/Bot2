from __future__ import annotations

import time

from app.config.settings import BotSettings
from app.data.quality import validate_bars_quality
from app.runtime.upgraded_bot import BrokerContext, UpgradedBot


class DummyMarketData:
    def __init__(self, bars: list[dict], spread_pctile: float = 20.0):
        self._bars = bars
        self._spread = spread_pctile

    def get_recent_bars(self, instrument: str, granularity: str, count: int = 120):
        return self._bars[-count:]

    def get_spread_pctile(self, instrument: str) -> float:
        return self._spread

    def get_liquidity_factor(self, instrument: str) -> float:
        return 0.9

    def has_near_event(self, instrument: str) -> bool:
        return False


def _bars(count: int = 180, start_ts: float | None = None, step: float = 60.0) -> list[dict]:
    out: list[dict] = []
    px = 1.0
    ts = start_ts if start_ts is not None else time.time() - (count * step)
    for _ in range(count):
        px += 0.0004
        out.append({"timestamp": ts, "open": px - 0.0001, "high": px + 0.0003, "low": px - 0.0003, "close": px})
        ts += step
    return out


def _settings() -> BotSettings:
    return BotSettings(
        instruments=["EUR_USD"],
        granularity="M5",
        min_signal_score=0.15,
        max_spread_pctile=85.0,
        max_positions=6,
        risk_budget_daily=0.015,
        cluster_risk_cap=0.01,
        min_trade_interval_sec=0,
        max_trade_interval_sec=120,
    )


def test_validate_quality_returns_reason_codes_for_block_and_degrade():
    bars = _bars()
    bars[81]["timestamp"] = bars[80]["timestamp"]
    bars[45]["close"] = -1.0

    result = validate_bars_quality("EUR_USD", bars, spread_pctile=97.0)

    assert result.status == "blocked"
    assert "data_quality_non_positive_price" in result.reason_codes
    assert "data_quality_timestamp_duplicate" in result.reason_codes
    assert "spread_outlier" in result.failing_rules


def test_runtime_blocks_instrument_on_quality_failures():
    bars = _bars()
    bars[81]["timestamp"] = bars[80]["timestamp"]
    market = DummyMarketData(bars)
    bot = UpgradedBot(settings=_settings())

    decisions = bot.run_cycle(market, BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={}))

    assert decisions == []
    block_events = [ev for ev in bot.events.events if ev.event_type == "data_quality_block"]
    assert len(block_events) == 1
    assert block_events[0].payload["instrument"] == "EUR_USD"
    assert "data_quality_timestamp_duplicate" in block_events[0].payload["reason_codes"]


def test_runtime_degrades_instrument_and_emits_reason_codes():
    stale_start = time.time() - 20_000
    bars = _bars(start_ts=stale_start)
    market = DummyMarketData(bars, spread_pctile=97.0)
    bot = UpgradedBot(settings=_settings())

    bot.run_cycle(market, BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={}))

    degraded_events = [ev for ev in bot.events.events if ev.event_type == "data_quality_degraded"]
    assert len(degraded_events) == 1
    reason_codes = degraded_events[0].payload["reason_codes"]
    assert "data_quality_stale_quotes" in reason_codes
    assert "data_quality_spread_outlier" in reason_codes
