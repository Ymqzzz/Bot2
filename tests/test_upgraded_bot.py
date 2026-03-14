from app.runtime.upgraded_bot import UpgradedBot, BrokerContext


class DummyMarketData:
    def __init__(self):
        self._bars = []
        px = 1.0
        for i in range(180):
            px += 0.0004
            self._bars.append({"open": px - 0.0001, "high": px + 0.0003, "low": px - 0.0003, "close": px})

    def get_recent_bars(self, instrument: str, granularity: str, count: int = 120):
        return self._bars[-count:]

    def get_spread_pctile(self, instrument: str) -> float:
        return 20.0

    def get_liquidity_factor(self, instrument: str) -> float:
        return 0.9

    def has_near_event(self, instrument: str) -> bool:
        return False


def test_upgraded_bot_generates_approved_decision():
    bot = UpgradedBot()
    market = DummyMarketData()
    ctx = BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={})

    decisions = bot.run_cycle(market, ctx)

    assert decisions
    assert any(d.get("approved") for d in decisions)
    assert bot.events.events


def test_killswitch_blocks_trading():
    bot = UpgradedBot()
    bot.kill_switch.activate("manual")
    market = DummyMarketData()
    ctx = BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={})

    decisions = bot.run_cycle(market, ctx)

    assert decisions == []
    assert any(ev.event_type == "signal_rejected" for ev in bot.events.events)
