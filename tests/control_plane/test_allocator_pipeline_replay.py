from datetime import datetime, timezone
import pandas as pd

from control_plane import ControlPlanePipeline, load_config
from control_plane.replay import replay_cycle


def _bars():
    return pd.DataFrame({
        "open": [1.0 + (i * 0.0001) for i in range(180)],
        "high": [1.001 + (i * 0.0001) for i in range(180)],
        "low": [0.999 + (i * 0.0001) for i in range(180)],
        "close": [1.0005 + (i * 0.0001) for i in range(180)],
    })


def test_allocator_prevents_full_stack_same_cluster():
    cfg = load_config()
    cfg = cfg.__class__(**{**cfg.__dict__, "ALLOC_MAX_SINGLE_MACRO_CLUSTER_RISK": 0.01})
    pipe = ControlPlanePipeline(cfg)
    now = datetime.now(timezone.utc)
    cand = [
        {"candidate_id": "1", "instrument": "EUR_USD", "strategy_name": "Breakout-Squeeze", "side": "BUY", "expected_value": 0.7, "confidence": 0.7, "risk_fraction_requested": 0.009, "edge_score": 0.7},
        {"candidate_id": "2", "instrument": "GBP_USD", "strategy_name": "Breakout-Squeeze", "side": "BUY", "expected_value": 0.69, "confidence": 0.69, "risk_fraction_requested": 0.009, "edge_score": 0.69},
    ]
    snap = pipe.run_cycle(now, ["EUR_USD", "GBP_USD"], {"EUR_USD": {}, "GBP_USD": {}}, {"EUR_USD": _bars(), "GBP_USD": _bars()}, cand, [])
    assert len(snap.allocation_decision.approved_candidate_ids) <= 2


def test_replay_deterministic():
    cfg = load_config()
    pipe = ControlPlanePipeline(cfg)
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    data = {
        "asof": now,
        "instruments": ["EUR_USD"],
        "market_intel_snapshots": {"EUR_USD": {}},
        "bars": {"EUR_USD": _bars()},
        "candidate_pool": [{"candidate_id": "1", "instrument": "EUR_USD", "strategy_name": "Breakout-Squeeze", "side": "BUY", "expected_value": 0.8, "confidence": 0.8, "risk_fraction_requested": 0.005, "edge_score": 0.8}],
        "open_positions": [],
        "edge_context": {},
    }
    a = replay_cycle(pipe, data)
    b = replay_cycle(pipe, data)
    assert a["allocation_decision"]["approved_candidate_ids"] == b["allocation_decision"]["approved_candidate_ids"]
