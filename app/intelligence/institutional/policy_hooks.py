from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from app.intelligence.institutional.schemas import (
    EnsembleDecision,
    FeatureGovernanceReport,
    InstitutionalDecision,
    MarketMemoryAssessment,
    PortfolioGraphReport,
    SessionDecision,
    StressReport,
)


@dataclass(frozen=True)
class PolicyThresholds:
    min_confidence: float = 0.40
    max_memory_fragility: float = 0.78
    min_stress_robustness: float = 0.42
    max_portfolio_concentration: float = 0.75
    min_feature_health: float = 0.30
    max_ensemble_conflict: float = 0.70


@dataclass(frozen=True)
class PolicyDecision:
    approved: bool
    score: float
    vetoes: list[str]
    warnings: list[str]
    metadata: dict[str, float] = field(default_factory=dict)


class MemoryPolicyHook:
    def evaluate(self, memory: MarketMemoryAssessment, thresholds: PolicyThresholds) -> tuple[bool, str | None, str | None]:
        if memory.fragility_score > thresholds.max_memory_fragility and memory.confidence > 0.35:
            return False, "memory_fragility_veto", None
        if memory.samples < 8:
            return True, None, "memory_sample_thin"
        return True, None, None


class StressPolicyHook:
    def evaluate(self, stress: StressReport, thresholds: PolicyThresholds) -> tuple[bool, str | None, str | None]:
        if stress.robustness_score < thresholds.min_stress_robustness:
            return False, "stress_robustness_veto", None
        if stress.distribution.p10_r < -0.5:
            return True, None, "stress_tail_warning"
        return True, None, None


class PortfolioPolicyHook:
    def evaluate(self, portfolio: PortfolioGraphReport, thresholds: PolicyThresholds) -> tuple[bool, str | None, str | None]:
        if portfolio.concentration_score > thresholds.max_portfolio_concentration:
            return False, "portfolio_concentration_veto", None
        if portfolio.fragility_score > 0.65:
            return True, None, "portfolio_fragility_warning"
        return True, None, None


class SessionPolicyHook:
    def evaluate(self, session: SessionDecision) -> tuple[bool, str | None, str | None]:
        if session.block_new_risk:
            return False, "session_block_veto", None
        if session.transition_risk > 0.60:
            return True, None, "session_transition_warning"
        return True, None, None


class FeaturePolicyHook:
    def evaluate(self, report: FeatureGovernanceReport, thresholds: PolicyThresholds) -> tuple[bool, str | None, str | None]:
        if report.critical_issues:
            return False, "feature_critical_veto", None
        if report.overall_health < thresholds.min_feature_health:
            return False, "feature_health_veto", None
        if report.quarantined_features:
            return True, None, "feature_quarantine_warning"
        return True, None, None


class EnsemblePolicyHook:
    def evaluate(self, ensemble: EnsembleDecision, thresholds: PolicyThresholds) -> tuple[bool, str | None, str | None]:
        if ensemble.inter_family_conflict > thresholds.max_ensemble_conflict:
            return False, "ensemble_conflict_veto", None
        if ensemble.confidence < 0.20:
            return True, None, "ensemble_low_confidence_warning"
        return True, None, None


class CompositePolicyEngine:
    def __init__(self, thresholds: PolicyThresholds | None = None) -> None:
        self.thresholds = thresholds or PolicyThresholds()
        self.memory = MemoryPolicyHook()
        self.stress = StressPolicyHook()
        self.portfolio = PortfolioPolicyHook()
        self.session = SessionPolicyHook()
        self.feature = FeaturePolicyHook()
        self.ensemble = EnsemblePolicyHook()

    def evaluate(
        self,
        *,
        confidence: float,
        memory: MarketMemoryAssessment,
        stress: StressReport,
        portfolio: PortfolioGraphReport,
        session: SessionDecision,
        features: FeatureGovernanceReport,
        ensemble: EnsembleDecision,
    ) -> PolicyDecision:
        vetoes: list[str] = []
        warnings: list[str] = []

        for passed, veto, warn in [
            self.memory.evaluate(memory, self.thresholds),
            self.stress.evaluate(stress, self.thresholds),
            self.portfolio.evaluate(portfolio, self.thresholds),
            self.session.evaluate(session),
            self.feature.evaluate(features, self.thresholds),
            self.ensemble.evaluate(ensemble, self.thresholds),
        ]:
            if not passed and veto:
                vetoes.append(veto)
            if warn:
                warnings.append(warn)

        if confidence < self.thresholds.min_confidence:
            vetoes.append("confidence_floor_veto")

        risk_score = mean(
            [
                memory.fragility_score,
                1.0 - stress.robustness_score,
                portfolio.fragility_score,
                session.transition_risk,
                1.0 - features.overall_health,
                ensemble.inter_family_conflict,
            ]
        )
        metadata = {
            "confidence": confidence,
            "risk_score": risk_score,
            "veto_count": float(len(vetoes)),
            "warning_count": float(len(warnings)),
        }

        approved = len(vetoes) == 0
        return PolicyDecision(approved=approved, score=max(0.0, 1.0 - risk_score), vetoes=vetoes, warnings=warnings, metadata=metadata)


class PolicyOverrideRegistry:
    def __init__(self) -> None:
        self._overrides: dict[str, str] = {}

    def set_override(self, key: str, value: str) -> None:
        self._overrides[key] = value

    def get_overrides(self) -> dict[str, str]:
        return dict(self._overrides)


class DecisionPolicyHooks:
    def __init__(self) -> None:
        self.engine = CompositePolicyEngine()
        self.overrides = PolicyOverrideRegistry()

    def apply(
        self,
        *,
        decision: InstitutionalDecision,
    ) -> PolicyDecision:
        result = self.engine.evaluate(
            confidence=decision.confidence,
            memory=decision.memory,
            stress=decision.stress,
            portfolio=decision.portfolio,
            session=decision.session,
            features=decision.feature_governance,
            ensemble=decision.ensemble,
        )

        ov = self.overrides.get_overrides()
        if ov.get("force_approve") == "true":
            return PolicyDecision(
                approved=True,
                score=result.score,
                vetoes=[],
                warnings=[*result.warnings, "force_approve_override"],
                metadata={**result.metadata, "override": 1.0},
            )
        if ov.get("force_block") == "true":
            return PolicyDecision(
                approved=False,
                score=result.score,
                vetoes=[*result.vetoes, "force_block_override"],
                warnings=result.warnings,
                metadata={**result.metadata, "override": -1.0},
            )
        return result


__all__ = [
    "CompositePolicyEngine",
    "DecisionPolicyHooks",
    "PolicyDecision",
    "PolicyOverrideRegistry",
    "PolicyThresholds",
]
