from __future__ import annotations

from typing import Protocol


class MarketDataProvider(Protocol):
    def get_recent_bars(self, instrument: str, granularity: str, count: int = 120) -> list[dict]:
        ...

    def get_spread_pctile(self, instrument: str) -> float:
        ...

    def get_liquidity_factor(self, instrument: str) -> float:
        ...

    def has_near_event(self, instrument: str) -> bool:
        ...
