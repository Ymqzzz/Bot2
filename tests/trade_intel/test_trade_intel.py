from trade_intel.classifiers import classify_entry_quality, classify_exit_quality, classify_trade_outcome
from trade_intel.config import TradeIntelConfig
from trade_intel.edge_decay import EdgeDecayEngine
from trade_intel.exits import SmartExitEngine
from trade_intel.pipeline import build_default_pipeline
from trade_intel.sizing import AdaptiveSizingEngine


def test_entry_quality_classification():
    label, score, reasons = classify_entry_quality(
        slippage_bps=0.5,
        spread_bps=1.0,
        distance_struct_bps=2.0,
        distance_profile_bps=2.0,
        move_spent_fraction=0.1,
        adverse_selection_score=0.0,
        passive_improvement=True,
    )
    assert label in {"excellent", "good"}
    assert score > 0.7
    assert isinstance(reasons, list)


def test_exit_quality_classification():
    label, score, _ = classify_exit_quality(
        captured_mfe_fraction=0.9,
        gaveback_fraction=0.1,
        exit_at_structure=True,
        exit_at_profile=False,
        due_to_time_stop=False,
        due_to_trailing=True,
        due_to_execution_dislocation=False,
    )
    assert label in {"excellent_capture", "good_structural_exit"}
    assert score > 0.7


def test_outcome_classification_fast_failure():
    label, *_ = classify_trade_outcome(
        realized_r=-1.0,
        entry_quality_score=0.2,
        exit_quality_score=0.3,
        fast_invalidated=True,
        execution_drag=False,
        timing_loss=False,
        regime_mismatch=False,
        exit_mismanaged=False,
    )
    assert label == "fast_thesis_failure"


def test_sizing_boundaries_and_block():
    cfg = TradeIntelConfig()
    engine = AdaptiveSizingEngine(cfg)
    d = engine.recommend_size(
        {"instrument": "EUR_USD", "strategy_name": "Breakout", "intel_quality_score": 0.9, "execution_feasibility_score": 0.9, "regime_alignment_score": 0.9},
        {"execution_risk_score": 0.1, "event_risk": False, "spread_expensive": False},
        {"available_risk_score": 1.0},
        [],
        {"session_edge_score": 0.8, "recent_performance_score": 0.8},
    )
    assert not d.block_trade
    assert cfg.SIZE_MULTIPLIER_MIN <= d.size_multiplier_total <= cfg.SIZE_MULTIPLIER_MAX

    b = engine.recommend_size(
        {"instrument": "EUR_USD", "strategy_name": "Breakout", "intel_quality_score": 0.01, "execution_feasibility_score": 0.5, "regime_alignment_score": 0.5},
        {"execution_risk_score": 0.1, "event_risk": False, "spread_expensive": False},
        {"available_risk_score": 1.0},
        [],
        {"session_edge_score": 0.5, "recent_performance_score": 0.5},
    )
    assert b.block_trade


def test_exit_engine_rules():
    cfg = TradeIntelConfig()
    ex = SmartExitEngine(cfg)
    plan = ex.build_initial_exit_plan({"trade_id": "t1", "setup_type": "breakout", "entry_price": 1.0, "stop_loss": 0.99, "side": "BUY"})
    assert plan.max_hold_seconds == cfg.BREAKOUT_MAX_HOLD_SECONDS
    assert ex.should_arm_break_even({}, {"r_multiple": 1.1, "structure_confirmed": True}, {"execution_risk_score": 0.1})


def test_edge_state_transition_logic():
    cfg = TradeIntelConfig()
    edge = EdgeDecayEngine(cfg)
    snap = edge.evaluate_scope("strategy", "A", {
        "sample_size": cfg.EDGE_MIN_SAMPLE_SIZE + 5,
        "expectancy_r": -0.4,
        "fast_invalidation_rate": 0.6,
        "execution_loss_rate": 0.4,
        "timing_loss_rate": 0.4,
        "rolling_drawdown_r": 2.0,
    })
    assert snap.edge_state in {"disabled", "degraded", "weak"}


def test_pipeline_prepare_and_close_roundtrip():
    pipeline = build_default_pipeline(TradeIntelConfig())
    prep = pipeline.prepare_trade(
        {
            "trade_id": "abc",
            "instrument": "EUR_USD",
            "strategy_name": "Breakout",
            "setup_type": "Breakout",
            "side": "BUY",
            "entry_price": 1.1,
            "stop_loss": 1.09,
            "take_profit": 1.12,
            "order_type": "MARKET",
            "confidence": 0.6,
            "ev_r": 0.3,
            "rr": 2.0,
            "intel_quality_score": 0.7,
            "entry_precision_score": 0.6,
            "execution_feasibility_score": 0.7,
            "regime_alignment_score": 0.7,
        },
        {"execution_risk_score": 0.2, "event_risk": False, "spread_expensive": False},
        {"available_risk_score": 0.8},
        {"session_name": "LONDON", "regime_name": "trend", "spread_regime": "normal", "recent_performance": {"session_edge_score": 0.6, "recent_performance_score": 0.6}},
    )
    assert not prep["block_trade"]
    pipeline.on_trade_open({"trade_id": prep["trade_id"], "entry_filled": 1.1001}, {})
    res = pipeline.on_trade_close(
        {"trade_id": prep["trade_id"]},
        {"realized_pnl": 10.0, "realized_r": 1.0, "bars_held": 5, "seconds_held": 60, "pnl_path": [1.0, 3.0, 2.0, 10.0], "spread_scores": [0.1], "vol_scores": [0.2]},
        {"spread_bps": 1.0, "distance_struct_bps": 3.0, "distance_profile_bps": 3.0},
    )
    assert res["status"] == "closed"
