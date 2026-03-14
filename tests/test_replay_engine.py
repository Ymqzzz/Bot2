from app.research.replay_engine import ReplayEngine
from app.runtime.upgraded_bot import UpgradedBot, BrokerContext


class DummyMarketData:
    def __init__(self):
        self._bars = []
        px = 1.0
        for _ in range(220):
            px += 0.00035
            self._bars.append({"open": px - 0.0001, "high": px + 0.0003, "low": px - 0.0003, "close": px})

    def get_recent_bars(self, instrument: str, granularity: str, count: int = 120):
        return self._bars[-count:]

    def get_spread_pctile(self, instrument: str) -> float:
        return 25.0

    def get_liquidity_factor(self, instrument: str) -> float:
        return 0.85

    def has_near_event(self, instrument: str) -> bool:
        return False


def test_replay_runs_and_counts_decisions():
    bot = UpgradedBot()
    market = DummyMarketData()
    ctx = BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={})

    out = ReplayEngine().run(bot, market, ctx, cycles=3)

    assert out.cycles == 3
    assert out.approved >= 1


def test_replay_emits_rate_and_reason_map():
    bot = UpgradedBot()
    market = DummyMarketData()
    ctx = BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={})

    out = ReplayEngine().run(bot, market, ctx, cycles=2)

    assert 0.0 <= out.approval_rate <= 1.0
    assert isinstance(out.block_reasons, dict)
