from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.adaptive.adaptive_score_breakdown import build_confidence_breakdown
from app.intelligence.adaptive.adaptive_types import AdaptiveDecision
from app.intelligence.adaptive.capital_efficiency_engine import CapitalEfficiencyEngine
from app.intelligence.adaptive.decision_narrative_generator import DecisionNarrativeGenerator
from app.intelligence.adaptive.edge_persistence_engine import EdgePersistenceEngine
from app.intelligence.adaptive.engine_negotiation_layer import EngineNegotiationLayer
from app.intelligence.adaptive.execution_memory_engine import ExecutionMemoryEngine
from app.intelligence.adaptive.input_contracts import AdaptiveInputContract
from app.intelligence.adaptive.outcome_router import AdaptiveOutcomeRouter
from app.intelligence.adaptive.path_dependency_engine import PathDependencyEngine
from app.intelligence.adaptive.policy import AdaptivePolicy
from app.intelligence.adaptive.reason_codes import AdaptiveReasonCode, map_capital_reasons
from app.intelligence.adaptive.reentry_engine import ReEntryEngine
from app.intelligence.adaptive.stateful_memory import AdaptiveStatefulMemory
from app.intelligence.adaptive.synthetic_adversary_engine import SyntheticAdversaryEngine
from app.intelligence.adaptive.telemetry_bus import AdaptiveTelemetryBus
from app.intelligence.adaptive.thesis_decomposition_engine import ThesisDecompositionEngine
from app.intelligence.models import AdaptiveIntelligenceState


@dataclass
class AdaptiveOperatingLayer:
    capital_efficiency: CapitalEfficiencyEngine = field(default_factory=CapitalEfficiencyEngine)
    thesis: ThesisDecompositionEngine = field(default_factory=ThesisDecompositionEngine)
    negotiation: EngineNegotiationLayer = field(default_factory=EngineNegotiationLayer)
    path_dependency: PathDependencyEngine = field(default_factory=PathDependencyEngine)
    reentry: ReEntryEngine = field(default_factory=ReEntryEngine)
    edge_persistence: EdgePersistenceEngine = field(default_factory=EdgePersistenceEngine)
    adversary: SyntheticAdversaryEngine = field(default_factory=SyntheticAdversaryEngine)
    execution_memory: ExecutionMemoryEngine = field(default_factory=ExecutionMemoryEngine)
    narrative: DecisionNarrativeGenerator = field(default_factory=DecisionNarrativeGenerator)
    telemetry: AdaptiveTelemetryBus = field(default_factory=AdaptiveTelemetryBus)
    memory: AdaptiveStatefulMemory = field(default_factory=AdaptiveStatefulMemory)
    contracts: AdaptiveInputContract = field(default_factory=AdaptiveInputContract)
    outcome_router: AdaptiveOutcomeRouter = field(default_factory=AdaptiveOutcomeRouter)

    def evaluate(
        self,
        *,
        timestamp,
        instrument: str,
        trace_id: str,
        features: dict[str, float],
        context: dict,
        candidate_strategy: str,
        base_confidence: float,
        base_size_multiplier: float,
        expected_edge: float,
    ) -> AdaptiveIntelligenceState:
        context = self.contracts.normalize_context(context)
        features = self.contracts.normalize_features(features)
        policy = AdaptivePolicy.from_context(context)
        capital = self.capital_efficiency.evaluate(
            features=features,
            context=context,
            candidate_strategy=candidate_strategy,
            expected_edge=expected_edge,
        )
        thesis = self.thesis.decompose(features=features, context=context)
        negotiation = self.negotiation.evaluate(context=context)
        path = self.path_dependency.evaluate(context=context)
        retry = self.reentry.evaluate(context=context)
        edge = self.edge_persistence.evaluate(context=context)
        adversary = self.adversary.evaluate(context=context)
        execution_memory = self.execution_memory.evaluate(context=context)

        fail_rate = self.memory.recent_fail_rate(window=int(context.get("adaptive_memory_window", 20)))
        fragility_avg = self.memory.recent_fragility_avg(window=int(context.get("adaptive_memory_window", 20)))
        memory_penalty = min(0.35, fail_rate * 0.25 + fragility_avg * 0.2)

        approved = (
            not negotiation.blocked
            and capital.capital_efficiency_score >= policy.min_capital_efficiency
            and edge.trust_multiplier >= policy.min_edge_trust
            and adversary.fragility_score <= policy.max_adversary_fragility
            and negotiation.total_penalty <= policy.max_negotiation_penalty
        )

        breakdown = build_confidence_breakdown(
            capital_efficiency=capital.capital_efficiency_score,
            thesis_expectancy=thesis.expectancy_score,
            negotiation_penalty=negotiation.total_penalty,
            path_decay=path.confidence_decay,
            adversary_fragility=adversary.fragility_score,
            memory_penalty=memory_penalty,
        )
        confidence_delta = breakdown.total
        size_delta = (
            capital.capital_efficiency_score * 0.12
            + edge.trust_multiplier * 0.1
            + retry.retry_size_multiplier * 0.06
            - negotiation.total_penalty * 0.1
            - path.stop_tightening_factor * 0.08
            - execution_memory.tactic_penalty * 0.05
            - memory_penalty * 0.5
        )

        adaptive_decision = AdaptiveDecision(
            approved=approved,
            confidence_delta=confidence_delta,
            size_delta=size_delta,
            reason_codes=[],
            telemetry={
                "adversary_fragility": adversary.fragility_score,
                "path_quality": path.path_quality_score,
                "thesis_decay": thesis.decay_score,
                "negotiation_penalty": negotiation.total_penalty,
                "memory_penalty": memory_penalty,
            },
        )

        reason_codes = [code.value for code in map_capital_reasons(capital.reason_codes)]
        if negotiation.blocked:
            reason_codes.append(AdaptiveReasonCode.NEGOTIATION_VETO.value)
        if path.health_label == "chaotic_path":
            reason_codes.append(AdaptiveReasonCode.PATH_CHAOTIC.value)
        if edge.expectancy_slope < 0:
            reason_codes.append(AdaptiveReasonCode.EDGE_DECAY.value)
        if adversary.fragility_score > 0.6:
            reason_codes.append(AdaptiveReasonCode.ADVERSARY_FRAGILE.value)
        if retry.allow_retry:
            reason_codes.append(AdaptiveReasonCode.RETRY_ALLOWED.value)
        if execution_memory.tactic_penalty > 0.55:
            reason_codes.append(AdaptiveReasonCode.EXECUTION_MEMORY_PENALTY.value)
        route = self.outcome_router.route(
            approved=approved,
            confidence_delta=confidence_delta,
            fragility=adversary.fragility_score,
            vetoed=negotiation.blocked,
        )
        reason_codes.append(f"ADAPTIVE_ROUTE_{route.action.upper()}")

        narrative = self.narrative.generate(
            approved=approved,
            confidence=min(1.0, max(0.0, base_confidence + confidence_delta)),
            size_multiplier=min(1.0, max(0.0, base_size_multiplier + size_delta)),
            supports=capital.reason_codes + ["THESIS_DOMINANT_" + thesis.dominant_thesis.upper()],
            objections=[o.message for o in negotiation.objections],
            penalties={
                "negotiation": negotiation.total_penalty,
                "path_decay": path.confidence_decay,
                "adversary_fragility": adversary.fragility_score,
                "crowding": edge.crowding_penalty,
                "memory_penalty": memory_penalty,
            },
            candidate_strategy=candidate_strategy,
            order_style=execution_memory.recommended_order_style,
            invalidations=[leg.invalidation_rule for leg in thesis.legs[:3]],
            veto_sources=negotiation.veto_sources,
        )

        state = AdaptiveIntelligenceState(
            timestamp=timestamp,
            instrument=instrument,
            trace_id=trace_id,
            confidence=min(1.0, max(0.0, base_confidence + confidence_delta)),
            sources=["adaptive_operating_layer"],
            capital_efficiency=capital.__dict__,
            thesis_vector={
                "dominant_thesis": thesis.dominant_thesis,
                "fragility_score": thesis.fragility_score,
                "decay_score": thesis.decay_score,
                "expectancy_score": thesis.expectancy_score,
                "legs": [leg.__dict__ for leg in thesis.legs],
            },
            negotiation={
                "blocked": negotiation.blocked,
                "total_penalty": negotiation.total_penalty,
                "veto_sources": negotiation.veto_sources,
                "dispute_trace": negotiation.dispute_trace,
            },
            path_dependency=path.__dict__,
            retry=retry.__dict__,
            edge_persistence=edge.__dict__,
            adversary=adversary.__dict__,
            execution_memory=execution_memory.__dict__,
            decision_narrative=narrative.__dict__,
            sandbox={
                "route": route.__dict__,
                "confidence_breakdown": breakdown.__dict__,
            },
            adaptive_approval=adaptive_decision.approved,
            adaptive_confidence_delta=adaptive_decision.confidence_delta,
            adaptive_size_delta=adaptive_decision.size_delta,
            reason_codes=reason_codes,
        )

        telemetry_event = {
            "trace_id": trace_id,
            "instrument": instrument,
            "approved": approved,
            "adversary_fragility": adversary.fragility_score,
            "memory_penalty": memory_penalty,
            "capital_efficiency_score": capital.capital_efficiency_score,
        }
        self.telemetry.emit(telemetry_event)
        self.memory.push(telemetry_event)
        return state
