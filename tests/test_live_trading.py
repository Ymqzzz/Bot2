from __future__ import annotations

from app.runtime.live_trading import LiveTrader


class _FakeBot:
    def __init__(self, decisions):
        self.decisions = decisions

    def run_cycle(self, _market_data, _context):
        return self.decisions


class _FakeBroker:
    def __init__(self):
        self.orders = []

    def get_account_summary(self):
        return {"NAV": "10000", "unrealizedPL": "0", "pl": "0"}

    def get_open_positions(self):
        return []

    def create_order(self, instrument: str, units: int):
        self.orders.append((instrument, units))
        return {"orderCreateTransaction": {"id": "1"}, "orderFillTransaction": {"id": "2"}}


class _FakeMarketData:
    pass


def test_live_trader_submits_only_approved_nonzero_orders():
    decisions = [
        {"approved": True, "proposal": {"instrument": "EUR_USD", "signed_units": 10}},
        {"approved": True, "proposal": {"instrument": "USD_JPY", "signed_units": 0}},
        {"approved": False, "proposal": {"instrument": "GBP_USD", "signed_units": 8}},
    ]
    broker = _FakeBroker()
    trader = LiveTrader(bot=_FakeBot(decisions), market_data=_FakeMarketData(), broker=broker)

    fills = trader.run_once()

    assert broker.orders == [("EUR_USD", 10)]
    assert fills[0]["instrument"] == "EUR_USD"
    assert fills[0]["units"] == 10
