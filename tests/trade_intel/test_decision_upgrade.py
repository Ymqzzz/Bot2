from trade_intel.config import TradeIntelConfig
from trade_intel.pipeline import build_default_pipeline
from trade_intel.decision_engine import build_decision_engine
from trade_intel.execution_simulator import ExecutionSimulator
from trade_intel.health_monitor import HealthMonitor
from trade_intel.regime_transition_model import RegimeTransitionModel
from trade_intel.signal_graph import SignalDependencyGraph


def test_decision_engine_declines_negative_edge():
    de = build_decision_engine()
    ex = ExecutionSimulator().estimate({"ev_r": 0.01}, {"spread_bps": 2.0, "volatility_score": 0.8})
    regime = RegimeTransitionModel().update({"regime_name": "trend", "regime_confidence": 0.8})
    sg = SignalDependencyGraph().analyze({"engine_signals": {"a": [1, 1, 1], "b": [1, 1, 1]}}, {})
    dist = de.build_distribution({"ev_r": 0.01, "confidence": 0.4}, ex, sg, regime, {})
    out = de.decide({"instrument": "EUR_USD"}, dist, ex, sg, regime, False, 1.0, [], "ASIA")
    assert not out.approved
    assert "DECISION_NEGATIVE_EDGE" in out.decline_reason_hierarchy


def test_health_monitor_circuit_breaker():
    hm = HealthMonitor()
    hs = hm.assess({"provider_lag_ms": 3000}, {"data_age_seconds": 300, "nan_feature_ratio": 0.35})
    assert hs.block_trading
    assert "HEALTH_CIRCUIT_BREAKER" in hs.reason_codes


def test_pipeline_prepare_trade_exposes_decision_outputs():
    pipeline = build_default_pipeline(TradeIntelConfig())
    prep = pipeline.prepare_trade(
        {
            "trade_id": "d1",
            "instrument": "EUR_USD",
            "strategy_name": "Breakout",
            "setup_type": "Breakout",
            "side": "BUY",
            "entry_price": 1.1,
            "stop_loss": 1.09,
            "take_profit": 1.12,
            "order_type": "MARKET",
            "confidence": 0.65,
            "ev_r": 0.45,
            "rr": 2.0,
            "intel_quality_score": 0.8,
            "entry_precision_score": 0.7,
            "execution_feasibility_score": 0.8,
            "regime_alignment_score": 0.7,
            "engine_signals": {"trend": [0.3, 0.4, 0.5], "momentum": [0.2, 0.1, 0.3]},
        },
        {"execution_risk_score": 0.2, "event_risk": False, "spread_expensive": False, "spread_bps": 0.8},
        {"available_risk_score": 0.8},
        {
            "session_name": "LONDON",
            "regime_name": "trend",
            "regime_confidence": 0.7,
            "spread_regime": "normal",
            "recent_performance": {"session_edge_score": 0.6, "recent_performance_score": 0.6},
        },
    )
    assert "decision" in prep
    assert "distribution" in prep
    assert "execution_estimate" in prep


def test_pipeline_blocks_when_health_fails():
    pipeline = build_default_pipeline(TradeIntelConfig())
    prep = pipeline.prepare_trade(
        {
            "trade_id": "d2",
            "instrument": "EUR_USD",
            "strategy_name": "Breakout",
            "setup_type": "Breakout",
            "side": "BUY",
            "entry_price": 1.1,
            "stop_loss": 1.09,
            "take_profit": 1.12,
            "confidence": 0.8,
            "ev_r": 0.5,
            "intel_quality_score": 0.8,
            "execution_feasibility_score": 0.8,
            "regime_alignment_score": 0.8,
            "engine_signals": {"trend": [1, 1, 1], "ma": [1, 1, 1]},
        },
        {"execution_risk_score": 0.2},
        {"available_risk_score": 0.9},
        {
            "session_name": "LONDON",
            "regime_name": "trend",
            "regime_confidence": 0.8,
            "data_age_seconds": 500,
            "nan_feature_ratio": 0.4,
            "recent_performance": {"session_edge_score": 0.8, "recent_performance_score": 0.8},
        },
    )
    assert prep["block_trade"]
