from trade_intel.child_order_scheduler import schedule_child_orders
from trade_intel.contextual_weight_memory import ContextualWeightMemory
from trade_intel.execution_simulator import ExecutionSimulator
from trade_intel.health_monitor import HealthMonitor
from trade_intel.performance_decay_model import PerformanceDecayModel
from trade_intel.regime_transition_model import RegimeTransitionModel
from trade_intel.signal_graph import SignalDependencyGraph
from trade_intel.trade_attribution_engine import LiveAttributionEngine


def test_regime_transition_with_conflicting_sources():
    model = RegimeTransitionModel()
    state = model.update(
        {
            "regime_name": "trend",
            "regime_confidence": 0.6,
            "regime_sources": {
                "hmm": ("mean_reversion", 0.8),
                "vol": ("volatile", 0.2),
            },
        }
    )
    assert state.current_regime in {"mean_reversion", "volatile", "trend"}
    assert 0.0 <= state.transition_risk <= 1.0


def test_signal_graph_feature_overlap_reduces_orthogonal_score():
    report = SignalDependencyGraph().analyze(
        {
            "engine_signals": {"a": [1, 2, 3], "b": [1, 2, 3], "c": [3, 2, 1]},
            "engine_features": {
                "a": ["ma", "slope", "rsi"],
                "b": ["ma", "slope", "rsi"],
                "c": ["vwap", "profile"],
            },
        },
        {"regime_name": "trend"},
    )
    assert report.orthogonal_score < 1.0
    assert report.cluster_count >= 1


def test_execution_simulator_adds_child_schedule():
    candidate = {"order_type": "MARKET", "order_qty": 5.0, "child_slices": 3, "urgency": "low"}
    est = ExecutionSimulator().estimate(candidate, {"spread_bps": 1.0, "volatility_score": 0.3})
    assert est.fill_probability > 0.0
    assert "child_order_schedule" in candidate
    assert abs(sum(candidate["child_order_schedule"]) - 5.0) < 1e-7


def test_health_monitor_drift_degrades_even_without_stale_data():
    monitor = HealthMonitor()
    hs = monitor.assess(
        {"provider_lag_ms": 0},
        {
            "data_age_seconds": 0,
            "live_metrics": {"win_rate": 0.2, "expectancy": -0.3},
            "expected_metrics": {"win_rate": 0.55, "expectancy": 0.2},
        },
    )
    assert hs.degraded
    assert any(r == "HEALTH_LIVE_BACKTEST_DRIFT" for r in hs.reason_codes)


def test_child_order_scheduler_distribution():
    sch = schedule_child_orders(10.0, 4, "normal")
    assert len(sch) == 4
    assert abs(sum(sch) - 10.0) < 1e-8


def test_decay_and_contextual_memory():
    decay = PerformanceDecayModel(half_life_trades=10)
    assert 0 < decay.decay_weight(5) < 1
    mem = ContextualWeightMemory()
    mem.update("trend_engine", "trend", "LONDON", "EUR_USD", 0.72)
    assert mem.get("trend_engine", "trend", "LONDON", "EUR_USD") >= 0.5


def test_live_attribution_tracks_opposers_and_confidence_error():
    engine = LiveAttributionEngine()
    out = engine.process_closed_trade(
        {
            "ev_r": 0.6,
            "regime": "trend",
            "session": "NY",
            "instrument": "EUR_USD",
            "supporting_engines": ["trend_a"],
            "opposing_engines": ["mean_rev_b"],
        },
        {"realized_r": -0.9},
    )
    assert "trend_a" in out.engine_trust
    assert "mean_rev_b" in out.engine_trust
    assert any(lbl in out.labels for lbl in {"ATTR_BAD_CALL", "ATTR_OPPOSER_WAS_RIGHT", "ATTR_MODEL_OVERCONFIDENT"})
