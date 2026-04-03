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
    assert len(bot.registry.plugins) >= 5
    market = DummyMarketData()
    ctx = BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={})

    decisions = bot.run_cycle(market, ctx)

    assert decisions
    assert any(d.get("approved") for d in decisions)
    approved = next(d for d in decisions if d.get("approved"))
    assert "sizing" in approved
    assert approved["proposal"]["signed_units"] != 0
    assert bot.events.events


def test_killswitch_blocks_trading():
    bot = UpgradedBot()
    bot.kill_switch.activate("manual")
    market = DummyMarketData()
    ctx = BrokerContext(nav=100_000.0, open_positions=[], corr_matrix={})

    decisions = bot.run_cycle(market, ctx)

    assert decisions == []
    assert any(ev.event_type == "signal_rejected" for ev in bot.events.events)



def test_pre_gate_risk_state_event_emitted():
    bot = UpgradedBot()
    market = DummyMarketData()
    ctx = BrokerContext(
        nav=100_000.0,
        open_positions=[],
        corr_matrix={},
        realized_pnl=120.0,
        unrealized_pnl=-20.0,
        equity_now=100_500.0,
    )

    bot.run_cycle(market, ctx)

    risk_events = [ev for ev in bot.events.events if ev.event_type == "risk_state_updated"]
    assert risk_events
    payload = risk_events[-1].payload
    assert payload["realized_pnl"] == 120.0
    assert payload["unrealized_pnl"] == -20.0
    assert payload["equity_now"] == 100_500.0


def test_pre_gate_risk_limits_emit_structured_block_event():
    bot = UpgradedBot()
    market = DummyMarketData()
    bot.gov_state.equity_peak = 100_000.0
    ctx = BrokerContext(
        nav=95_000.0,
        open_positions=[],
        corr_matrix={},
        realized_pnl=-2_500.0,
        unrealized_pnl=0.0,
        equity_now=80_000.0,
    )

    decisions = bot.run_cycle(market, ctx)

    assert decisions == []
    blocked = [ev for ev in bot.events.events if ev.event_type == "risk_blocked"]
    assert blocked
    payload = blocked[-1].payload
    assert payload["reason"] in {"daily_loss_limit", "max_drawdown_limit"}
    assert payload["current_drawdown_pct"] > 0
    assert payload["loss_budget_usage_pct"] > 0
