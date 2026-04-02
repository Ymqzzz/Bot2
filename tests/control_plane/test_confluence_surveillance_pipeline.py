from datetime import datetime, timezone

import pandas as pd

from control_plane.confluence_engine import AdaptiveConfluenceEngine
from control_plane.config import ControlPlaneConfig
from control_plane.pipeline import ControlPlanePipeline
from control_plane.surveillance_engine import SurveillanceEngine


def _bars(n: int = 120) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [1.0 + (i * 0.0001) for i in range(n)],
            "high": [1.0004 + (i * 0.0001) for i in range(n)],
            "low": [0.9996 + (i * 0.0001) for i in range(n)],
            "close": [1.0002 + (i * 0.0001) for i in range(n)],
        }
    )


def test_confluence_engine_scales_risk_with_score():
    cfg = ControlPlaneConfig()
    eng = AdaptiveConfluenceEngine(cfg)

    hi = eng.evaluate_candidate(
        {
            "candidate_id": "high",
            "strategy_name": "Trend-Pullback",
            "expected_value": 0.9,
            "confidence": 0.9,
            "edge_score": 0.9,
        },
        regime_score=0.9,
        event_score=1.0,
        execution_score=0.9,
        correlation_penalty=0.0,
    )
    lo = eng.evaluate_candidate(
        {
            "candidate_id": "low",
            "strategy_name": "Trend-Pullback",
            "expected_value": 0.1,
            "confidence": 0.1,
            "edge_score": 0.1,
        },
        regime_score=0.2,
        event_score=0.2,
        execution_score=0.2,
        correlation_penalty=0.8,
    )
    assert hi.confluence_score > lo.confluence_score
    assert hi.risk_multiplier > lo.risk_multiplier


def test_surveillance_blocks_toxic_candidate():
    cfg = ControlPlaneConfig()
    eng = SurveillanceEngine(cfg)

    d = eng.evaluate_candidate(
        {"candidate_id": "c1", "instrument": "EUR_USD"},
        {"toxicity_score": 0.95},
    )
    assert not d.allow_trade
    assert d.risk_multiplier == 0.0


def test_pipeline_applies_surveillance_gating():
    pipe = ControlPlanePipeline(config=ControlPlaneConfig(), calendar_provider=lambda: [])
    snapshot = pipe.run_cycle(
        asof=datetime(2025, 1, 1, tzinfo=timezone.utc),
        instruments=["EUR_USD"],
        market_intel_snapshots={
            "EUR_USD": {
                "spread_dislocation": 0.05,
                "spread_bps": 1.0,
                "velocity": 0.3,
                "toxicity_score": 0.95,
            }
        },
        bars={"EUR_USD": _bars()},
        candidate_pool=[
            {
                "candidate_id": "cid-toxic",
                "instrument": "EUR_USD",
                "strategy_name": "Trend-Pullback",
                "side": "BUY",
                "setup_type": "Trend-Pullback",
                "expected_value": 0.8,
                "confidence": 0.8,
                "risk_fraction_requested": 0.005,
                "edge_score": 0.8,
            }
        ],
        open_positions=[],
        edge_context={},
    )

    assert "cid-toxic" not in snapshot.execution_decisions
    assert "SURVEILLANCE_BLOCK_TOXIC_FLOW" in snapshot.reason_codes
