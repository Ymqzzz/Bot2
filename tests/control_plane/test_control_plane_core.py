from datetime import datetime, timezone, timedelta

import pandas as pd

from control_plane.config import ControlPlaneConfig
from control_plane.correlation import CorrelationEngine
from control_plane.event_engine import EventEngine
from control_plane.execution_intel import ExecutionIntelligenceEngine
from control_plane.models import AllocationCandidate
from control_plane.order_tactics import OrderTacticPlanner
from control_plane.pipeline import ControlPlanePipeline
from control_plane.portfolio_allocator import PortfolioAllocator
from control_plane.regime_engine import RegimeEngine


def _bars(n=120, drift=0.0002):
    close = [1 + i * drift for i in range(n)]
    return pd.DataFrame({"close": close, "high": [c + 0.0005 for c in close], "low": [c - 0.0005 for c in close]})


def test_regime_classification_trend_expansion():
    engine = RegimeEngine(ControlPlaneConfig())
    event = EventEngine().build_event_decision(datetime.now(timezone.utc), ["EUR_USD"], {})
    dec = engine.classify_instrument_regime("EUR_USD", {"spread_z": 0.1}, _bars(), event)
    assert dec.regime_name in {"trend_expansion", "compression_pre_breakout", "uncertain_mixed", "rotation_mean_reversion"}


def test_event_phase_lockout():
    asof = datetime.now(timezone.utc)
    cal = lambda: [{"title": "US CPI", "currency": "USD", "impact": "high", "scheduled_ts": asof + timedelta(minutes=5)}]
    ev = EventEngine(calendar_provider=cal).build_event_decision(asof, ["EUR_USD"], {})
    assert ev.event_phase == "pre_event_lockout"
    assert not ev.allow_mean_reversion


def test_allocator_blocks_usd_concentration():
    cfg = ControlPlaneConfig(ALLOC_MAX_USD_NET_EXPOSURE=0.01)
    alloc = PortfolioAllocator(cfg)
    state = alloc.build_portfolio_state([], [], {})
    c = AllocationCandidate("c1", "EUR_USD", "Breakout-Squeeze", "BUY", "breakout", 0.8, 0.7, 0.02, None, 0.8, 0.8, 0.8, 0.8, 0.5, "anti_usd", {"USD": -1.0}, None, 0.9, False, [])
    d = alloc.allocate([c], state)
    assert c.candidate_id in d.blocked_candidate_ids or c.candidate_id in d.resized_candidate_ids


def test_execution_blocks_late_entry():
    cfg = ControlPlaneConfig(EXECUTION_MAX_LATE_ENTRY_RISK=0.2)
    exe = ExecutionIntelligenceEngine(cfg)
    reg = RegimeEngine(cfg).classify_instrument_regime("EUR_USD", {}, _bars(), EventEngine().build_event_decision(datetime.now(timezone.utc), ["EUR_USD"], {}))
    cand = AllocationCandidate("c1", "EUR_USD", "Breakout-Squeeze", "BUY", "breakout", 0.5, 0.6, 0.01, None, 0.8, 0.8, 0.8, 0.8, 0.6, "anti_usd", {"USD": -1}, None, None, False, [])
    ed = exe.evaluate_entry(cand, {"breakout_mag": 1.0, "persistence": 1.0, "spread_bps": 0.5}, reg, EventEngine().build_event_decision(datetime.now(timezone.utc), ["EUR_USD"], {}), {})
    assert not ed.allow_entry


def test_pipeline_deterministic_replay():
    asof = datetime(2025, 1, 1, tzinfo=timezone.utc)
    pipe = ControlPlanePipeline(ControlPlaneConfig(), calendar_provider=lambda: [])
    cand = AllocationCandidate("c1", "EUR_USD", "Breakout-Squeeze", "BUY", "breakout", 0.7, 0.7, 0.01, None, 0.8, 0.7, 0.7, 0.7, 0.6, "anti_usd", {"USD": -1}, None, None, False, [])
    kwargs = dict(asof=asof, instrument_snapshots={"EUR_USD": {"spread_bps": 0.2}}, bars={"EUR_USD": _bars()}, candidate_pool=[cand], open_positions=[])
    s1 = pipe.run_cycle(**kwargs).to_flat_dict()
    s2 = pipe.run_cycle(**kwargs).to_flat_dict()
    assert s1["event_decision"]["event_state"] == s2["event_decision"]["event_state"]


def test_correlation_macro_cluster():
    c = CorrelationEngine()
    assert c.cluster_macro_expression({"instrument": "EUR_USD", "side": "BUY"}) == "anti_usd"


def test_tactic_plan_generation():
    planner = OrderTacticPlanner()
    cand = AllocationCandidate("c1", "EUR_USD", "Breakout-Squeeze", "BUY", "breakout", 0.7, 0.7, 0.01, None, 0.8, 0.7, 0.7, 0.7, 0.6, "anti_usd", {"USD": -1}, None, None, False, [])
    pipe = ControlPlanePipeline(calendar_provider=lambda: [])
    snap = pipe.run_cycle(instrument_snapshots={"EUR_USD": {}}, bars={"EUR_USD": _bars()}, candidate_pool=[cand], open_positions=[])
    reg = list(snap.regime_decisions.values())[0]
    ex = snap.execution_decisions["c1"]
    t = planner.build_tactic_plan(cand, ex, reg, snap.event_decision)
    assert t.tactic_type
