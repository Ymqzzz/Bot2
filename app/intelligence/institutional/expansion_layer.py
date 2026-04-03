from __future__ import annotations

from datetime import datetime
import uuid

from app.intelligence.institutional.audit_registry import DecisionAuditLog, ModelRegistry
from app.intelligence.institutional.decision_explainability import DecisionExplainabilityEngine
from app.intelligence.institutional.ensemble_coordination import EnsembleCoordinator
from app.intelligence.institutional.feature_governance import FeatureGovernance
from app.intelligence.institutional.market_memory_engine import MarketMemoryEngine
from app.intelligence.institutional.policy_hooks import DecisionPolicyHooks
from app.intelligence.institutional.portfolio_interaction_graph import PortfolioInteractionGraph
from app.intelligence.institutional.scenario_generation import ForwardStressEngine, ScenarioGenerator
from app.intelligence.institutional.session_intelligence import SessionIntelligenceEngine
from app.intelligence.institutional.telemetry_backend import OpsSnapshotBuilder, TelemetryBus
from app.intelligence.institutional.timeframe_alignment_engine import MultiTimeframeAlignmentEngine
from app.intelligence.institutional.trade_lifecycle_manager import TradeLifecycleManager
from app.intelligence.institutional.schemas import (
    Direction,
    EventWindow,
    FeatureGovernanceReport,
    FeatureReference,
    HealthState,
    InstitutionalDecision,
    MemoryQuery,
    PositionNode,
    ReasonCode,
    SetupRecord,
    TelemetryEvent,
    ThesisVote,
    TimeframeState,
    TradeProposal,
)


class InstitutionalExpansionLayer:
    """Coordinator for the institutional expansion pack.

    This layer composes 10+ subsystems and now also includes:
    - policy hooks for post-score governance decisions
    - explanation builder for operator-facing attribution diagnostics
    """

    def __init__(self) -> None:
        self.memory = MarketMemoryEngine()
        self.scenario_generator = ScenarioGenerator()
        self.stress_engine = ForwardStressEngine()
        self.alignment = MultiTimeframeAlignmentEngine()
        self.portfolio = PortfolioInteractionGraph()
        self.lifecycle = TradeLifecycleManager()
        self.session = SessionIntelligenceEngine()
        self.feature_governance = FeatureGovernance()
        self.model_registry = ModelRegistry()
        self.audit_log = DecisionAuditLog()
        self.ensemble = EnsembleCoordinator()
        self.telemetry = TelemetryBus()
        self.ops_snapshot_builder = OpsSnapshotBuilder(self.telemetry)
        self.policy_hooks = DecisionPolicyHooks()
        self.explainability = DecisionExplainabilityEngine()

    def ingest_memory(self, records: list[SetupRecord]) -> None:
        for record in records:
            self.memory.ingest(record)

    def register_feature_reference(
        self,
        *,
        feature: str,
        mean: float,
        std: float,
        lower: float,
        upper: float,
        critical: bool,
        dependencies: list[str] | None = None,
    ) -> None:
        self.feature_governance.register_reference(
            FeatureReference(
                feature=feature,
                mean=mean,
                std=std,
                lower=lower,
                upper=upper,
                critical=critical,
            )
        )
        if dependencies:
            self.feature_governance.register_dependency(feature, dependencies)

    def evaluate_trade(
        self,
        *,
        proposal: TradeProposal,
        timeframe_states: list[TimeframeState],
        open_positions: list[PositionNode],
        thesis_votes: list[ThesisVote],
        event_windows: list[EventWindow] | None = None,
        now: datetime | None = None,
    ) -> InstitutionalDecision:
        ts = now or datetime.utcnow()
        reasons: list[str] = []
        penalties: dict[str, float] = {}
        contributors: dict[str, float] = {}
        approval_path: list[str] = []

        memory_query = MemoryQuery(
            setup_type=proposal.setup_type,
            regime=proposal.regime,
            session=proposal.session,
            instrument=proposal.instrument,
            direction=proposal.side,
            compression_score=proposal.features.get("compression_score", proposal.features.get("compression", 0.5)),
            volatility_state=str(proposal.features.get("volatility_state", "normal")),
            post_news_state=str(proposal.features.get("post_news_state", "none")),
            microstructure_tag=str(proposal.features.get("microstructure_tag", "normal")),
        )
        memory = self.memory.assess(memory_query)
        contributors["memory"] = 1.0 - memory.fragility_score
        approval_path.append("market_memory")
        if memory.samples < 8:
            reasons.append(ReasonCode.MEMORY_INSUFFICIENT_HISTORY.value)
            penalties["memory_insufficient"] = 0.04
        if memory.fragility_score > 0.68 and memory.confidence > 0.30:
            reasons.append(ReasonCode.MEMORY_SETUP_FRAGILE.value)
            penalties["memory_fragile"] = 0.15

        scenarios = self.scenario_generator.generate(proposal, n_paths=60)
        stress = self.stress_engine.evaluate(proposal, scenarios)
        contributors["stress"] = stress.robustness_score
        approval_path.append("forward_stress")
        if stress.fragile:
            reasons.append(ReasonCode.STRESS_ROBUSTNESS_LOW.value)
            penalties["stress_fragile"] = 0.20
        if stress.distribution.worst_r < -2.0:
            reasons.append(ReasonCode.STRESS_WORST_CASE_EXCESSIVE.value)
            penalties["stress_tail"] = 0.10

        alignment = self.alignment.evaluate(timeframe_states)
        contributors["alignment"] = alignment.alignment_score
        approval_path.append("multi_timeframe_alignment")
        if alignment.veto:
            reasons.append(ReasonCode.TIMEFRAME_CONFLICT.value)
            penalties["timeframe_conflict"] = 0.20
        if alignment.htf_veto:
            reasons.append(ReasonCode.TIMEFRAME_HTF_VETO.value)
            penalties["timeframe_htf"] = 0.16

        candidate_position = PositionNode(
            position_id=proposal.trade_id,
            instrument=proposal.instrument,
            thesis_family=proposal.thesis_family,
            quantity=proposal.quantity,
            notional=proposal.features.get("notional", proposal.quantity * proposal.entry),
            beta_risk_on=proposal.features.get("beta_risk_on", 0.0),
            usd_beta=proposal.features.get("usd_beta", 0.0),
            rates_beta=proposal.features.get("rates_beta", 0.0),
            commodities_beta=proposal.features.get("commodities_beta", 0.0),
            stop_distance_r=proposal.features.get("stop_distance_r", 1.0),
            regime_tag=proposal.regime,
            event_vulnerability=proposal.features.get("event_vulnerability", 0.0),
        )
        portfolio = self.portfolio.evaluate(open_positions, candidate_position)
        contributors["portfolio"] = 1.0 - portfolio.fragility_score
        approval_path.append("portfolio_interaction_graph")
        if portfolio.concentration_score > 0.70:
            reasons.append(ReasonCode.PORTFOLIO_CONCENTRATION.value)
            penalties["portfolio_concentration"] = 0.16
        if portfolio.fragility_score > 0.72:
            reasons.append(ReasonCode.PORTFOLIO_CLUSTER_FRAGILITY.value)
            penalties["portfolio_fragility"] = 0.12

        session = self.session.assess(now=ts, external_event_windows=event_windows)
        contributors["session"] = 1.0 - session.transition_risk * 0.5 - session.liquidity_penalty * 0.3
        approval_path.append("session_event_intelligence")
        if session.block_new_risk:
            reasons.append(ReasonCode.SESSION_RISK_WINDOW.value)
            penalties["session_event"] = 0.25
        if session.liquidity_penalty > 0.35:
            reasons.append(ReasonCode.SESSION_LOW_LIQUIDITY.value)
            penalties["session_liquidity"] = 0.08

        self.feature_governance.update_observation(proposal.features)
        feature_report: FeatureGovernanceReport = self.feature_governance.evaluate(proposal.features)
        contributors["feature_governance"] = feature_report.overall_health
        approval_path.append("feature_governance")
        if feature_report.quarantined_features:
            reasons.append(ReasonCode.FEATURE_DRIFT.value)
            penalties["feature_quarantine"] = 0.18
        if feature_report.critical_issues:
            reasons.append(ReasonCode.FEATURE_MISSING_CRITICAL.value)
            penalties["feature_critical"] = 0.20
        if feature_report.overall_health < 0.30:
            reasons.append(ReasonCode.FEATURE_INSTABILITY.value)
            penalties["feature_instability"] = 0.12

        ensemble = self.ensemble.combine(thesis_votes)
        contributors["ensemble"] = ensemble.confidence
        approval_path.append("synthetic_ensemble")
        if ensemble.inter_family_conflict > 0.60:
            reasons.append(ReasonCode.ENSEMBLE_DIRECTION_CONFLICT.value)
            penalties["ensemble_conflict"] = 0.12
        if ensemble.confidence < 0.22:
            reasons.append(ReasonCode.ENSEMBLE_LOW_CONSENSUS.value)
            penalties["ensemble_low"] = 0.08

        base_confidence = (
            contributors["memory"] * 0.20
            + contributors["stress"] * 0.24
            + contributors["alignment"] * 0.18
            + contributors["portfolio"] * 0.13
            + contributors["session"] * 0.09
            + contributors["feature_governance"] * 0.08
            + contributors["ensemble"] * 0.08
        )

        total_penalty = sum(penalties.values())
        confidence = max(0.0, min(1.0, base_confidence - total_penalty))

        direction_multiplier = 1.0
        if ensemble.net_direction == Direction.FLAT:
            direction_multiplier *= 0.85
        elif ensemble.net_direction != proposal.side:
            direction_multiplier *= 0.65

        size_multiplier = max(
            0.0,
            min(
                1.2,
                confidence
                * session.size_multiplier
                * (1.0 - portfolio.concentration_score * 0.35)
                * direction_multiplier,
            ),
        )

        preliminary_decision = InstitutionalDecision(
            approved=confidence > 0.40,
            confidence=confidence,
            size_multiplier=size_multiplier,
            reason_codes=reasons,
            memory=memory,
            stress=stress,
            alignment=alignment,
            portfolio=portfolio,
            session=session,
            feature_governance=feature_report,
            ensemble=ensemble,
        )

        policy = self.policy_hooks.apply(decision=preliminary_decision)
        approved = preliminary_decision.approved and policy.approved

        for warning in policy.warnings:
            if warning not in reasons:
                reasons.append(warning)

        health = HealthState.HEALTHY if approved else HealthState.DEGRADED
        self.telemetry.emit(
            TelemetryEvent(
                source="institutional_expansion",
                heartbeat_ts=ts,
                confidence=confidence,
                latency_ms=4.2,
                health=health,
                payload={
                    "trade_id": proposal.trade_id,
                    "reason_codes": reasons,
                    "size_multiplier": size_multiplier,
                    "policy_score": policy.score,
                },
            )
        )

        explanation = self.explainability.build(
            final_confidence=confidence,
            size_multiplier=size_multiplier,
            approved=approved,
            reason_codes=reasons,
            penalties=penalties,
            memory=memory,
            stress=stress,
            alignment=alignment,
            portfolio=portfolio,
            session=session,
            feature_report=feature_report,
            ensemble=ensemble,
        )

        decision_id = str(uuid.uuid4())
        self.audit_log.append(
            decision_id=decision_id,
            timestamp=ts,
            trade_id=proposal.trade_id,
            model_versions=self.model_registry.snapshot(),
            features=proposal.features,
            regime_snapshot={
                "regime": proposal.regime,
                "session": proposal.session,
                "alignment_bias": alignment.refinement_bias.value,
                "session_state": session.active_session,
            },
            signal_contributors=contributors,
            penalties={**penalties, "policy_veto_count": float(len(policy.vetoes))},
            overrides={
                "policy_approved": str(policy.approved),
                "policy_vetoes": ",".join(policy.vetoes),
                "ensemble_direction": ensemble.net_direction.value,
                "explainability_gross": str(round(explanation.diagnostics.get("gross_score", 0.0), 6)),
            },
            reason_codes=reasons,
            approval_path=[*approval_path, "policy_hooks", "explainability"],
            approved=approved,
            confidence=confidence,
        )

        return InstitutionalDecision(
            approved=approved,
            confidence=confidence,
            size_multiplier=size_multiplier,
            reason_codes=reasons,
            memory=memory,
            stress=stress,
            alignment=alignment,
            portfolio=portfolio,
            session=session,
            feature_governance=feature_report,
            ensemble=ensemble,
        )


__all__ = ["InstitutionalExpansionLayer"]
