from __future__ import annotations

from execution_engine import ExecutionStats


class ExecutionCostModel:
    def __init__(self):
        self.stats = ExecutionStats(maxlen=1000)

    def observe_fill(self, instrument: str, spread: float, expected_price: float, filled_price: float) -> None:
        self.stats.record_fill(instrument, spread, expected_price, filled_price)

    def snapshot(self, instrument: str) -> dict:
        return self.stats.summary(instrument)
