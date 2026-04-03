from datetime import datetime, timedelta

from app.intelligence.institutional_layer import (
    Direction,
    EventWindow,
    HealthState,
    InstitutionalExpansionLayer,
    PositionNode,
    PositionState,
    ReasonCode,
    SetupRecord,
    TelemetryEvent,
    ThesisVote,
    TimeframeState,
    TradeProposal,
)


def _proposal(**overrides):
    base = TradeProposal(
        trade_id="T-100",
        instrument="EURUSD",
        side=Direction.LONG,
        entry=1.1000,
        stop=1.0980,
        target=1.1045,
        quantity=1.2,
        setup_type="breakout_continuation",
        regime="trend",
        session="london_open",
        strategy="trend_breakout_v3",
        thesis_family="trend_following",
        expected_holding_bars=24,
        features={
            "compression_score": 0.25,
            "volatility_state": 1.0,
            "post_news_state": 0.0,
            "microstructure_tag": 1.0,
            "spread": 0.00008,
            "drift_alpha": 0.21,
            "structure_support": 0.73,
            "breakout_quality": 0.80,
            "beta_risk_on": 0.2,
            "usd_beta": -0.4,
            "rates_beta": 0.05,
            "commodities_beta": 0.04,
            "stop_distance_r": 1.2,
            "event_vulnerability": 0.25,
            "notional": 120000,
            "signal_strength": 0.72,
            "flow_quality": 0.66,
        },
    )
    return TradeProposal(**{**base.__dict__, **overrides})


def _memory_record(i: int, pnl: float, stop_out: bool) -> SetupRecord:
    return SetupRecord(
        record_id=f"rec-{i}",
        setup_type="breakout_continuation",
        regime="trend",
        session="london_open",
        instrument="EURUSD",
        direction=Direction.LONG,
        compression_score=0.24,
        volatility_state="normal",
        post_news_state="none",
        microstructure_tag="clean",
        entry_quality=0.7,
        pnl_r=pnl,
        mfe_r=max(0.0, pnl + 0.2),
        mae_r=abs(min(0.0, pnl)) + 0.1,
        stop_out=stop_out,
        holding_bars=8,
        created_at=datetime(2025, 1, 1),
    )


def test_end_to_end_decision_and_audit_snapshot() -> None:
    layer = InstitutionalExpansionLayer()
    layer.model_registry.register(model_name="entry_model", version="3.4.1", training_data_tag="wf_2026q1")
    layer.model_registry.register(model_name="risk_model", version="1.2.0", training_data_tag="risk_2026q1")

    for i in range(30):
        layer.ingest_memory([_memory_record(i, pnl=0.45 if i % 4 else -0.25, stop_out=i % 4 == 0)])

    layer.register_feature_reference(feature="signal_strength", mean=0.65, std=0.1, lower=0.25, upper=0.95, critical=True)
    layer.register_feature_reference(feature="flow_quality", mean=0.60, std=0.1, lower=0.20, upper=0.95, critical=False)

    decision = layer.evaluate_trade(
        proposal=_proposal(),
        timeframe_states=[
            TimeframeState("1m", Direction.LONG, 0.78, 0.8, 0.75, 0.45),
            TimeframeState("5m", Direction.LONG, 0.80, 0.84, 0.78, 0.48),
            TimeframeState("15m", Direction.LONG, 0.74, 0.8, 0.77, 0.5),
            TimeframeState("1h", Direction.LONG, 0.70, 0.72, 0.74, 0.52),
        ],
        open_positions=[
            PositionNode("P-1", "GBPUSD", "trend_following", 1.0, 95000, 0.2, -0.3, 0.04, 0.05, 1.1, "trend", 0.2)
        ],
        thesis_votes=[
            ThesisVote("trend_plugin", "trend_following", Direction.LONG, 0.71, 0.9),
            ThesisVote("breakout_plugin", "breakout_continuation", Direction.LONG, 0.67, 0.8),
        ],
        now=datetime(2026, 3, 2, 8, 30),
    )

    assert decision.confidence > 0.0
    assert layer.audit_log.latest() is not None
    assert layer.audit_log.latest().model_versions["entry_model"] == "3.4.1"


def test_memory_fragility_and_feature_quarantine_add_reason_codes() -> None:
    layer = InstitutionalExpansionLayer()

    for i in range(45):
        layer.ingest_memory([_memory_record(i, pnl=-0.85 if i % 3 else 0.1, stop_out=True)])

    layer.register_feature_reference(feature="signal_strength", mean=0.60, std=0.05, lower=0.2, upper=0.9, critical=True)

    decision = layer.evaluate_trade(
        proposal=_proposal(features={"signal_strength": 1.5}),
        timeframe_states=[TimeframeState("1m", Direction.LONG, 0.7, 0.6, 0.6, 0.8)],
        open_positions=[],
        thesis_votes=[ThesisVote("trend", "trend_following", Direction.LONG, 0.55, 0.5)],
        now=datetime(2026, 3, 2, 8, 30),
    )

    assert ReasonCode.MEMORY_SETUP_FRAGILE.value in decision.reason_codes
    assert (ReasonCode.FEATURE_DRIFT.value in decision.reason_codes) or (ReasonCode.FEATURE_INSTABILITY.value in decision.reason_codes)


def test_session_event_window_blocks_new_risk() -> None:
    layer = InstitutionalExpansionLayer()
    now = datetime(2026, 3, 6, 17, 5)
    windows = [
        EventWindow(
            label="NFP",
            start=now - timedelta(minutes=2),
            end=now + timedelta(minutes=8),
            severity=0.95,
            relevance=1.0,
        )
    ]

    decision = layer.evaluate_trade(
        proposal=_proposal(),
        timeframe_states=[TimeframeState("1m", Direction.LONG, 0.8, 0.7, 0.7, 0.6)],
        open_positions=[],
        thesis_votes=[ThesisVote("trend", "trend_following", Direction.LONG, 0.65, 0.8)],
        event_windows=windows,
        now=now,
    )

    assert not decision.approved
    assert ReasonCode.SESSION_RISK_WINDOW.value in decision.reason_codes


def test_portfolio_concentration_reason_code_triggered() -> None:
    layer = InstitutionalExpansionLayer()
    open_positions = [
        PositionNode("A", "GBPUSD", "trend_following", 3.0, 300000, 0.65, -0.62, 0.2, 0.1, 0.8, "trend", 0.6),
        PositionNode("B", "AUDUSD", "trend_following", 2.5, 260000, 0.70, -0.60, 0.25, 0.12, 0.85, "trend", 0.6),
    ]

    p = _proposal()
    decision = layer.evaluate_trade(
        proposal=_proposal(quantity=2.8, features={**p.features, "notional": 280000, "beta_risk_on": 0.7, "usd_beta": -0.65}),
        timeframe_states=[TimeframeState("1m", Direction.LONG, 0.8, 0.8, 0.8, 0.45)],
        open_positions=open_positions,
        thesis_votes=[ThesisVote("trend", "trend_following", Direction.LONG, 0.7, 0.8)],
        now=datetime(2026, 3, 2, 8, 30),
    )

    assert ReasonCode.PORTFOLIO_CONCENTRATION.value in decision.reason_codes


def test_trade_lifecycle_state_transitions() -> None:
    layer = InstitutionalExpansionLayer()
    snap = layer.lifecycle.stage(
        trade_id="L-1",
        confidence=0.7,
        entry_price=1.10,
        stop_price=1.098,
        target_price=1.104,
    )
    assert snap.state == PositionState.STAGED

    updated = layer.lifecycle.update(
        trade_id="L-1",
        timestamp=datetime(2026, 3, 2, 9, 0),
        fill_ratio=1.0,
        current_price=1.1018,
        bars_open=10,
        thesis_score=0.75,
        event_risk_score=0.1,
        expected_holding_bars=20,
    )
    assert updated.state in {PositionState.ACTIVE, PositionState.TRAILING}

    invalidated = layer.lifecycle.update(
        trade_id="L-1",
        timestamp=datetime(2026, 3, 2, 12, 0),
        fill_ratio=1.0,
        current_price=1.0975,
        bars_open=28,
        thesis_score=0.1,
        event_risk_score=0.2,
        expected_holding_bars=20,
    )
    assert invalidated.state == PositionState.EMERGENCY_EXIT_CANDIDATE


def test_telemetry_and_ops_snapshot_contains_alerts() -> None:
    layer = InstitutionalExpansionLayer()
    ts = datetime(2026, 3, 2, 10, 0)
    layer.telemetry.emit(
        TelemetryEvent(
            source="risk_engine",
            heartbeat_ts=ts,
            confidence=0.2,
            latency_ms=140.0,
            health=HealthState.DEGRADED,
            payload={"reason": "slow_data_feed"},
        )
    )

    snapshot = layer.ops_snapshot_builder.build()
    assert snapshot.active_alerts
    assert "risk_engine" in snapshot.degraded_sources
