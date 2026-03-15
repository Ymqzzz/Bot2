from datetime import datetime, timezone

import pandas as pd

from control_plane.config import ControlPlaneConfig, load_config
from control_plane.models import AllocationCandidate
from control_plane.pipeline import ControlPlanePipeline


def _bars(n: int = 120) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [1.0 + (i * 0.0001) for i in range(n)],
            "high": [1.0004 + (i * 0.0001) for i in range(n)],
            "low": [0.9996 + (i * 0.0001) for i in range(n)],
            "close": [1.0002 + (i * 0.0001) for i in range(n)],
        }
    )


def test_pipeline_init_matches_main_global_bootstrap_pattern():
    cfg = load_config()
    pipe = ControlPlanePipeline(cfg)
    assert pipe.config is cfg


def test_pipeline_cycle_matches_apply_control_plane_pattern():
    cfg = ControlPlaneConfig()
    pipe = ControlPlanePipeline(config=cfg, calendar_provider=lambda: [])
    snapshot = pipe.run_cycle(
        asof=datetime(2025, 1, 1, tzinfo=timezone.utc),
        instruments=["EUR_USD"],
        market_intel_snapshots={"EUR_USD": {"spread_dislocation": 0.05, "spread_bps": 1.0, "velocity": 0.3}},
        bars={"EUR_USD": _bars()},
        candidate_pool=[
            {
                "candidate_id": "cid-1",
                "instrument": "EUR_USD",
                "strategy_name": "Trend-Pullback",
                "side": "BUY",
                "setup_type": "Trend-Pullback",
                "expected_value": 0.6,
                "confidence": 0.6,
                "risk_fraction_requested": 0.005,
                "edge_score": 0.6,
            }
        ],
        open_positions=[],
        edge_context={},
    )
    assert "cid-1" in snapshot.execution_decisions


def test_pipeline_cycle_matches_control_plane_select_plan_pattern():
    pipe = ControlPlanePipeline(config=ControlPlaneConfig(), calendar_provider=lambda: [])
    candidate = AllocationCandidate(
        candidate_id="cid-2",
        instrument="EUR_USD",
        strategy_name="Trend-Pullback",
        side="BUY",
        setup_type="Trend-Pullback",
        expected_value=0.55,
        confidence=0.55,
        risk_fraction_requested=0.005,
        risk_fraction_capped=None,
        regime_score=0.5,
        event_score=0.5,
        execution_score=0.5,
        edge_score=0.5,
        portfolio_fit_score=0.5,
        macro_cluster_key="anti_usd",
        currency_exposure_map={"USD": -0.005, "EUR": 0.005},
        correlation_bucket=None,
        priority_score=0.5,
        blocked=False,
        block_reason_codes=[],
    )
    snapshot = pipe.run_cycle(
        instrument_snapshots={"EUR_USD": {"spread_bps": 0.3, "event_risk": 0.0}},
        bars={"EUR_USD": _bars()},
        candidate_pool=[candidate],
        open_positions=[],
        edge_context={},
    )
    assert snapshot.event_decision.event_phase in {"normal", "pre_event_lockout", "release_window", "post_event_digestion", "spread_normalization_pending", "headline_risk"}
