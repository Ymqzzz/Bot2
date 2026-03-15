from app.monitoring.events import EventBus
from app.monitoring.repository import create_event_repository


def test_event_bus_persists_and_queries(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'events.db'}"
    repo = create_event_repository(db_url)
    bus = EventBus(repository=repo, cache_size=2)

    trace = bus.new_trace()
    bus.emit("signal_emitted", trace, {"instrument": "EUR_USD", "strategy": "trend", "score": 0.81})
    bus.emit("signal_rejected", trace, {"instrument": "EUR_USD", "reason": "spread_wide", "dislocation": 1.4})
    bus.emit("risk_blocked", trace, {"instrument": "EUR_USD", "reason_code": "daily_budget"})
    bus.emit("order_submitted", trace, {"instrument": "EUR_USD", "strategy": "trend", "qty": 1000})
    bus.emit("fill", trace, {"instrument": "EUR_USD", "slippage_bps": 1.25, "filled_price": 1.101, "expected_price": 1.1008})
    bus.emit("exit", trace, {"instrument": "EUR_USD", "reason": "tp_hit"})
    bus.emit("stop_update", trace, {"instrument": "EUR_USD", "reason": "trail"})

    counts = bus.candidate_counts()
    assert counts.signal_emitted == 1
    assert counts.signal_rejected == 1
    assert counts.risk_blocked == 1
    assert counts.order_submitted == 1
    assert counts.fill == 1
    assert counts.exit == 1
    assert counts.stop_updated == 1

    reasons = bus.rejection_reasons(limit=5)
    assert reasons[0]["reason_code"] in {"spread_wide", "daily_budget"}

    slippage = bus.slippage_trends("EUR_USD")
    assert len(slippage) == 1
    assert slippage[0]["fill_count"] == 1
    assert slippage[0]["avg_slippage_bps"] == 1.25

    assert len(bus.events) == 2


def test_event_bus_cache_only_mode():
    bus = EventBus(repository=None, cache_size=3)

    trace = bus.new_trace()
    bus.emit("signal_rejected", trace, {"reason": "policy"})
    bus.emit("risk_blocked", trace, {"reason_code": "risk"})
    bus.emit("fill", trace, {"instrument": "GBP_USD", "slippage_bps": 2.0})

    reasons = bus.rejection_reasons()
    assert reasons[0]["count"] == 1
    assert {row["reason_code"] for row in reasons} == {"policy", "risk"}

    slippage = bus.slippage_trends("GBP_USD")
    assert slippage and slippage[0]["avg_slippage_bps"] == 2.0
