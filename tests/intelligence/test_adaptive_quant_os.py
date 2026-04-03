from datetime import datetime

from app.intelligence.adaptive.capital_efficiency_engine import CapitalEfficiencyEngine
from app.intelligence.adaptive.engine_negotiation_layer import EngineNegotiationLayer
from app.intelligence.adaptive.input_contracts import AdaptiveInputContract
from app.intelligence.adaptive.operating_layer import AdaptiveOperatingLayer
from app.intelligence.adaptive.outcome_router import AdaptiveOutcomeRouter
from app.intelligence.adaptive.path_dependency_engine import PathDependencyEngine
from app.intelligence.adaptive.research_sandbox import ResearchSandbox
from app.intelligence.orchestrator import IntelligenceOrchestrator


class _MomentumPlugin:
    name = "momentum_sandbox_plugin"

    def evaluate(self, features: dict[str, float], context: dict) -> float:
        return min(1.0, max(0.0, features.get("directional_persistence", 0.0) * 0.8 + context.get("sandbox_stability", 0.0) * 0.2))


def _bars(n: int = 120) -> list[dict]:
    price = 1.2
    out: list[dict] = []
    for _ in range(n):
        price += 0.0002
        out.append({"open": price - 0.0001, "high": price + 0.0002, "low": price - 0.00015, "close": price})
    return out


def test_capital_efficiency_penalizes_opportunity_cost_and_margin_stress() -> None:
    engine = CapitalEfficiencyEngine()
    features = {"realized_vol": 0.9, "atr_percentile": 0.95}
    context = {
        "account_equity": 100000,
        "free_margin": 12000,
        "candidate_notional": 25000,
        "effective_leverage": 6,
        "strategy_concentration": 0.7,
        "correlation_stress": 0.75,
        "stress_drawdown": 0.55,
        "queued_trades": [
            {"expected_edge": 0.2, "incremental_margin": 1000},
            {"expected_edge": 0.1, "incremental_margin": 400},
        ],
        "capital_lockup_by_family": {"trend": 9000.0},
    }
    report = engine.evaluate(features=features, context=context, candidate_strategy="breakout", expected_edge=0.05)
    assert report.margin_headroom_ratio < 0.2
    assert "MARGIN_HEADROOM_COMPRESSED" in report.reason_codes


def test_negotiation_layer_surfaces_vetoes() -> None:
    layer = EngineNegotiationLayer()
    outcome = layer.evaluate(
        context={
            "setup_type": "breakout",
            "microstructure_quality": 0.2,
            "sweep_trap_risk": 0.85,
            "regime_instability": 0.9,
        }
    )
    assert outcome.blocked
    assert len(outcome.veto_sources) >= 1
    assert any("surveillance" in v or "regime" in v for v in outcome.veto_sources)


def test_path_dependency_detects_chaotic_evolution() -> None:
    engine = PathDependencyEngine()
    report = engine.evaluate(
        context={
            "pnl_path": [0.0, 1.2, -0.8, 1.5, -1.1, 1.0, -0.9],
            "initial_thrust": 0.7,
            "sustained_move": 0.2,
            "stop_zone_probes": 4,
            "near_invalidation_ratio": 0.8,
        }
    )
    assert report.health_label in {"chaotic_path", "fragile_grind"}
    assert report.confidence_decay > 0.2


def test_research_sandbox_keeps_plugins_paper_only() -> None:
    sandbox = ResearchSandbox()
    plugin = _MomentumPlugin()
    result = sandbox.run_plugin(
        plugin,
        features={"directional_persistence": 0.9},
        context={"sandbox_samples": 50, "sandbox_stability": 0.85},
    )
    assert result.paper_mode_only
    assert result.candidate_module == plugin.name


def test_orchestrator_produces_adaptive_state() -> None:
    orch = IntelligenceOrchestrator()
    features = {
        "atr_percentile": 0.6,
        "realized_vol": 0.45,
        "bar_overlap": 0.25,
        "directional_persistence": 0.75,
        "breakout_follow_through": 0.72,
        "spread_percentile": 0.25,
        "4h_slope": 0.7,
        "1h_slope": 0.65,
        "15m_slope": 0.55,
        "5m_slope": 0.5,
        "1m_slope": 0.48,
        "4h_momentum": 0.7,
        "1h_momentum": 0.65,
        "15m_momentum": 0.6,
        "5m_momentum": 0.56,
        "1m_momentum": 0.51,
        "4h_structure_quality": 0.75,
        "1h_structure_quality": 0.7,
        "15m_structure_quality": 0.65,
        "5m_structure_quality": 0.6,
        "1m_structure_quality": 0.55,
    }
    context = {
        "strategy_performance": {"trend": {"sample_size": 50, "win_rate": 0.58, "expectancy": 0.18, "drawdown": 0.2, "payoff_ratio": 1.4}},
        "cross_asset": {"dxy_change": -0.001, "rates_change": 0.001, "risk_on": 0.3},
        "analog_history": [],
        "expected_edge": 0.12,
        "account_equity": 100000,
        "free_margin": 45000,
        "candidate_notional": 12000,
        "effective_leverage": 10,
        "queued_trades": [{"expected_edge": 0.08, "incremental_margin": 900}],
        "execution_records": [{"passive_quality": 0.7, "aggressive_quality": 0.55, "slippage_bps": 1.8, "cancel_success": 0.8}],
        "session": "london",
        "pnl_path": [0.0, 0.3, 0.5, 0.7, 0.95],
        "near_invalidation_ratio": 0.1,
        "setup_type": "breakout",
        "microstructure_quality": 0.65,
        "sweep_trap_risk": 0.25,
        "regime_instability": 0.2,
    }

    snapshot = orch.build_snapshot(
        instrument="EURUSD",
        bars=_bars(),
        features=features,
        context=context,
        candidate_strategy="trend",
        raw_confidence=0.63,
        timestamp=datetime(2026, 4, 1),
    )

    assert snapshot.adaptive is not None
    assert "capital_efficiency_score" in snapshot.adaptive.capital_efficiency
    assert "dominant_thesis" in snapshot.adaptive.thesis_vector
    assert isinstance(snapshot.adaptive.adaptive_approval, bool)


def test_operating_layer_persists_memory_and_telemetry() -> None:
    layer = AdaptiveOperatingLayer()
    context = {
        "account_equity": 100000,
        "free_margin": 50000,
        "candidate_notional": 9000,
        "effective_leverage": 10,
        "queued_trades": [],
        "execution_records": [],
        "setup_type": "breakout",
        "microstructure_quality": 0.65,
        "sweep_trap_risk": 0.2,
        "regime_instability": 0.2,
    }
    features = {"directional_persistence": 0.7, "atr_percentile": 0.4, "realized_vol": 0.35}

    for idx in range(3):
        state = layer.evaluate(
            timestamp=datetime(2026, 4, 2),
            instrument="EURUSD",
            trace_id=f"trace-{idx}",
            features=features,
            context=context,
            candidate_strategy="trend",
            base_confidence=0.6,
            base_size_multiplier=0.5,
            expected_edge=0.1,
        )
        assert state.decision_narrative

    recent = layer.telemetry.recent(limit=5)
    assert len(recent) == 3
    assert all("trace_id" in event for event in recent)
    assert layer.memory.recent_fail_rate(window=10) >= 0.0


def test_orchestrator_respects_adaptive_policy_override() -> None:
    orch = IntelligenceOrchestrator()
    snapshot = orch.build_snapshot(
        instrument="EURUSD",
        bars=_bars(60),
        features={"directional_persistence": 0.5, "realized_vol": 0.95, "atr_percentile": 0.95, "spread_percentile": 0.7},
        context={
            "strategy_performance": {},
            "cross_asset": {},
            "analog_history": [],
            "adaptive_policy": {"min_capital_efficiency": 0.95, "max_adversary_fragility": 0.2},
            "account_equity": 100000,
            "free_margin": 10000,
            "candidate_notional": 45000,
            "effective_leverage": 5,
            "microstructure_quality": 0.2,
            "setup_type": "breakout",
            "sweep_trap_risk": 0.9,
            "regime_instability": 0.85,
        },
        candidate_strategy="trend",
        raw_confidence=0.7,
        timestamp=datetime(2026, 4, 2),
    )
    assert snapshot.adaptive is not None
    assert not snapshot.adaptive.adaptive_approval
    assert any(code.startswith("ADAPTIVE_") for code in snapshot.adaptive.reason_codes)


def test_input_contract_normalizes_sparse_payloads() -> None:
    contract = AdaptiveInputContract()
    context = contract.normalize_context({})
    features = contract.normalize_features({})
    assert context["account_equity"] >= 1.0
    assert context["candidate_notional"] >= 1.0
    assert "directional_persistence" in features


def test_outcome_router_routes_veto_and_throttle_paths() -> None:
    router = AdaptiveOutcomeRouter()
    blocked = router.route(approved=False, confidence_delta=-0.3, fragility=0.9, vetoed=True)
    throttled = router.route(approved=True, confidence_delta=-0.01, fragility=0.6, vetoed=False)
    assert blocked.action == "block"
    assert throttled.action == "throttle"
