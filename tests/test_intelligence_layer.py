from datetime import datetime

from app.intelligence.orchestrator import IntelligenceOrchestrator


def _bars_trend(n: int = 180):
    out = []
    px = 1.10
    for _ in range(n):
        px += 0.0003
        out.append({"open": px - 0.0001, "high": px + 0.00025, "low": px - 0.0002, "close": px})
    return out


def test_orchestrator_builds_snapshot_with_all_states() -> None:
    orch = IntelligenceOrchestrator()
    bars = _bars_trend()
    features = {
        "atr_percentile": 0.65,
        "realized_vol": 0.55,
        "bar_overlap": 0.22,
        "directional_persistence": 0.82,
        "breakout_follow_through": 0.74,
        "spread_percentile": 0.2,
        "false_breakout_rate": 0.15,
        "volatility_noise": 0.2,
        "4h_slope": 0.75,
        "1h_slope": 0.7,
        "15m_slope": 0.6,
        "5m_slope": 0.58,
        "1m_slope": 0.56,
        "4h_momentum": 0.75,
        "1h_momentum": 0.7,
        "15m_momentum": 0.66,
        "5m_momentum": 0.6,
        "1m_momentum": 0.58,
        "4h_structure_quality": 0.8,
        "1h_structure_quality": 0.78,
        "15m_structure_quality": 0.72,
        "5m_structure_quality": 0.68,
        "1m_structure_quality": 0.62,
        "4h_persistence": 0.82,
        "1h_persistence": 0.8,
        "15m_persistence": 0.76,
        "5m_persistence": 0.72,
        "1m_persistence": 0.68,
    }
    context = {
        "near_event": False,
        "minutes_to_event": 9999,
        "minutes_since_event": 9999,
        "event_severity": 0.0,
        "event_relevance": 0.0,
        "slippage_percentile": 0.2,
        "execution_cost": 0.15,
        "strategy_performance": {
            "trend": {"sample_size": 60, "win_rate": 0.62, "expectancy": 0.22, "drawdown": 0.18, "payoff_ratio": 1.6}
        },
        "cross_asset": {"dxy_change": -0.002, "rates_change": 0.001, "risk_on": 0.4},
        "analog_history": [
            {
                "alignment": 0.8,
                "health": 0.75,
                "event": 0.1,
                "quality": 0.72,
                "regime": "breakout_environment",
                "structure_phase": "expansion_leg",
                "liquidity_context": "high_signal",
                "sweep_type": "external_sweep_acceptance",
                "outcome": 1.4,
                "strategy": "trend",
            },
            {"alignment": 0.7, "health": 0.65, "event": 0.2, "quality": 0.6, "regime": "trend", "outcome": 0.9, "strategy": "trend"},
        ],
        "trace_id": "trace-test-1",
    }

    snap = orch.build_snapshot(
        instrument="EURUSD",
        bars=bars,
        features=features,
        context=context,
        candidate_strategy="trend",
        raw_confidence=0.66,
        timestamp=datetime(2026, 1, 1),
    )

    assert snap.uncertainty is not None
    assert snap.trade_quality is not None
    assert snap.trade_quality.alignment_score >= 0
    assert snap.liquidity.most_significant_pool != "none"
    assert snap.structure.current_phase != "unknown"
    assert 0.0 <= snap.uncertainty.uncertainty_score <= 1.0
    assert 0.0 <= snap.trade_quality.quality_score <= 1.0
    assert 0.0 <= snap.calibration.calibrated_confidence <= 1.0


def test_orchestrator_degrades_with_missing_cross_asset_and_history() -> None:
    orch = IntelligenceOrchestrator()
    bars = _bars_trend(120)
    features = {"bar_overlap": 0.7, "directional_persistence": 0.3, "breakout_follow_through": 0.2, "spread_percentile": 0.9}

    snap = orch.build_snapshot(
        instrument="GBPUSD",
        bars=bars,
        features=features,
        context={"strategy_performance": {}, "cross_asset": {}, "analog_history": []},
        candidate_strategy="mean_reversion",
        raw_confidence=0.8,
    )

    assert snap.cross_asset.confirmation_label == "missing"
    assert snap.analog.comparable_cases == 0
    assert snap.analog.insufficient_history_flag
    assert snap.uncertainty.uncertainty_score > 0.0
    assert snap.calibration.calibration_bucket in {"penalized", "neutral", "boosted"}
