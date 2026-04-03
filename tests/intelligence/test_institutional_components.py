from datetime import datetime

from app.intelligence.institutional.audit_registry import ReproducibilityBundle
from app.intelligence.institutional.decision_explainability import DecisionExplainabilityEngine
from app.intelligence.institutional.policy_hooks import DecisionPolicyHooks
from app.intelligence.institutional.schemas import (
    AlignmentReport,
    Direction,
    EnsembleDecision,
    FamilyConsensus,
    FeatureGovernanceReport,
    MarketMemoryAssessment,
    PortfolioGraphReport,
    SessionDecision,
    StressDistribution,
    StressReport,
)


def _decision_inputs():
    memory = MarketMemoryAssessment(
        samples=24,
        weighted_win_rate=0.57,
        weighted_expectancy_r=0.22,
        weighted_stop_out_rate=0.34,
        weighted_mfe_r=0.72,
        weighted_mae_r=0.33,
        mean_holding_bars=9.5,
        fragility_score=0.38,
        confidence=0.8,
    )

    stress = StressReport(
        path_count=60,
        robustness_score=0.62,
        fragility_score=0.35,
        fragile=False,
        distribution=StressDistribution([], 0.24, 0.2, -0.15, -0.2, -0.8, 0.95),
    )

    alignment = AlignmentReport(
        alignment_score=0.67,
        contradiction_severity=0.25,
        htf_veto=False,
        veto=False,
        refinement_bias=Direction.LONG,
    )

    portfolio = PortfolioGraphReport(
        node_count=3,
        edge_count=2,
        concentration_score=0.45,
        same_thesis_ratio=0.55,
        factor_crowding_score=0.40,
        stop_overlap_score=0.35,
        fragility_score=0.42,
    )

    session = SessionDecision(
        active_session="london_open",
        edge_multiplier=1.0,
        size_multiplier=0.95,
        block_new_risk=False,
        transition_risk=0.4,
        liquidity_penalty=0.1,
    )

    feature_report = FeatureGovernanceReport(
        overall_health=0.72,
        quarantined_features=[],
        critical_issues=[],
        by_feature={},
    )

    ensemble = EnsembleDecision(
        net_direction=Direction.LONG,
        confidence=0.61,
        inter_family_conflict=0.2,
        family_consensus=[
            FamilyConsensus("trend_following", Direction.LONG, 0.71, 0.15, 3),
            FamilyConsensus("breakout_continuation", Direction.LONG, 0.58, 0.2, 2),
        ],
    )
    return memory, stress, alignment, portfolio, session, feature_report, ensemble


def test_explainability_engine_builds_component_scores() -> None:
    memory, stress, alignment, portfolio, session, feature_report, ensemble = _decision_inputs()
    engine = DecisionExplainabilityEngine()
    explanation = engine.build(
        final_confidence=0.58,
        size_multiplier=0.72,
        approved=True,
        reason_codes=["ensemble_low_consensus"],
        penalties={"ensemble_low": 0.08},
        memory=memory,
        stress=stress,
        alignment=alignment,
        portfolio=portfolio,
        session=session,
        feature_report=feature_report,
        ensemble=ensemble,
    )

    assert explanation.component_scores
    assert explanation.diagnostics["gross_score"] > 0
    assert "ensemble_low_consensus" in explanation.reason_code_explanations


def test_policy_hooks_apply_veto_on_feature_critical_issue() -> None:
    memory, stress, alignment, portfolio, session, feature_report, ensemble = _decision_inputs()
    hooks = DecisionPolicyHooks()

    from app.intelligence.institutional.schemas import InstitutionalDecision

    bad_feature_report = FeatureGovernanceReport(
        overall_health=0.5,
        quarantined_features=["signal_strength"],
        critical_issues=["signal_strength"],
        by_feature={},
    )
    decision = InstitutionalDecision(
        approved=True,
        confidence=0.65,
        size_multiplier=0.8,
        reason_codes=[],
        memory=memory,
        stress=stress,
        alignment=alignment,
        portfolio=portfolio,
        session=session,
        feature_governance=bad_feature_report,
        ensemble=ensemble,
    )

    policy = hooks.apply(decision=decision)
    assert not policy.approved
    assert "feature_critical_veto" in policy.vetoes


def test_reproducibility_bundle_hash_stability() -> None:
    a = ReproducibilityBundle.feature_hash({"a": 1.23456789, "b": 2.0})
    b = ReproducibilityBundle.feature_hash({"b": 2.0, "a": 1.23456789})
    assert a == b

    c = ReproducibilityBundle.regime_hash({"regime": "trend", "timestamp": datetime(2026, 3, 3, 8, 0).isoformat()})
    d = ReproducibilityBundle.regime_hash({"timestamp": datetime(2026, 3, 3, 8, 0).isoformat(), "regime": "trend"})
    assert c == d
