from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from app.intelligence.institutional.schemas import (
    AlignmentReport,
    EnsembleDecision,
    FeatureGovernanceReport,
    MarketMemoryAssessment,
    PortfolioGraphReport,
    SessionDecision,
    StressReport,
)


@dataclass(frozen=True)
class DecisionComponentScore:
    component: str
    raw_score: float
    weight: float
    weighted_score: float
    penalty: float
    narrative: str


@dataclass(frozen=True)
class DecisionExplanation:
    final_confidence: float
    size_multiplier: float
    approval: bool
    component_scores: list[DecisionComponentScore]
    reason_code_explanations: dict[str, str]
    diagnostics: dict[str, float] = field(default_factory=dict)


class ReasonCodeExplainer:
    def __init__(self) -> None:
        self._messages: dict[str, str] = {
            "memory_setup_fragile": "Historically similar setups under this context show elevated failure density.",
            "memory_insufficient_history": "Historical analog coverage is thin, reducing prior reliability.",
            "stress_robustness_low": "Scenario stress paths show weak robustness in plausible adverse conditions.",
            "stress_worst_case_excessive": "Tail scenarios include extreme downside that exceeds tolerance bands.",
            "timeframe_conflict": "Directional states across timeframes conflict beyond policy threshold.",
            "timeframe_htf_veto": "Higher timeframe context vetoed lower timeframe execution intent.",
            "portfolio_concentration": "Portfolio graph indicates concentration in shared thesis/factor exposure.",
            "portfolio_cluster_fragility": "Cross-position stress clusters imply elevated liquidation fragility.",
            "session_risk_window": "Current session or event window is configured as risk-restrictive.",
            "session_low_liquidity": "Liquidity profile is below threshold and increases execution fragility.",
            "feature_drift": "Feature governance detected out-of-band distribution drift.",
            "feature_missing_critical": "Critical features are missing or quarantined.",
            "feature_instability": "Aggregate feature stability fell below minimum confidence policy.",
            "ensemble_direction_conflict": "Thesis families disagree on direction or confidence.",
            "ensemble_low_consensus": "Thesis family consensus confidence is weak.",
        }

    def explain(self, reason_codes: list[str]) -> dict[str, str]:
        return {code: self._messages.get(code, "No explanation registered.") for code in reason_codes}


class DecisionAttributionBuilder:
    def build(
        self,
        *,
        memory: MarketMemoryAssessment,
        stress: StressReport,
        alignment: AlignmentReport,
        portfolio: PortfolioGraphReport,
        session: SessionDecision,
        feature_report: FeatureGovernanceReport,
        ensemble: EnsembleDecision,
        penalties: dict[str, float],
    ) -> list[DecisionComponentScore]:
        components: list[DecisionComponentScore] = []

        components.append(
            DecisionComponentScore(
                component="market_memory",
                raw_score=1.0 - memory.fragility_score,
                weight=0.20,
                weighted_score=(1.0 - memory.fragility_score) * 0.20,
                penalty=penalties.get("memory_fragile", 0.0) + penalties.get("memory_insufficient", 0.0),
                narrative=self._memory_narrative(memory),
            )
        )

        components.append(
            DecisionComponentScore(
                component="forward_stress",
                raw_score=stress.robustness_score,
                weight=0.24,
                weighted_score=stress.robustness_score * 0.24,
                penalty=penalties.get("stress_fragile", 0.0) + penalties.get("stress_tail", 0.0),
                narrative=self._stress_narrative(stress),
            )
        )

        components.append(
            DecisionComponentScore(
                component="multi_timeframe_alignment",
                raw_score=alignment.alignment_score,
                weight=0.18,
                weighted_score=alignment.alignment_score * 0.18,
                penalty=penalties.get("timeframe_conflict", 0.0) + penalties.get("timeframe_htf", 0.0),
                narrative=self._alignment_narrative(alignment),
            )
        )

        components.append(
            DecisionComponentScore(
                component="portfolio_interaction_graph",
                raw_score=1.0 - portfolio.fragility_score,
                weight=0.13,
                weighted_score=(1.0 - portfolio.fragility_score) * 0.13,
                penalty=penalties.get("portfolio_concentration", 0.0) + penalties.get("portfolio_fragility", 0.0),
                narrative=self._portfolio_narrative(portfolio),
            )
        )

        session_raw = max(0.0, 1.0 - session.transition_risk * 0.5 - session.liquidity_penalty * 0.3)
        components.append(
            DecisionComponentScore(
                component="session_event_intelligence",
                raw_score=session_raw,
                weight=0.09,
                weighted_score=session_raw * 0.09,
                penalty=penalties.get("session_event", 0.0) + penalties.get("session_liquidity", 0.0),
                narrative=self._session_narrative(session),
            )
        )

        components.append(
            DecisionComponentScore(
                component="feature_governance",
                raw_score=feature_report.overall_health,
                weight=0.08,
                weighted_score=feature_report.overall_health * 0.08,
                penalty=penalties.get("feature_quarantine", 0.0)
                + penalties.get("feature_critical", 0.0)
                + penalties.get("feature_instability", 0.0),
                narrative=self._feature_narrative(feature_report),
            )
        )

        components.append(
            DecisionComponentScore(
                component="synthetic_ensemble",
                raw_score=ensemble.confidence,
                weight=0.08,
                weighted_score=ensemble.confidence * 0.08,
                penalty=penalties.get("ensemble_conflict", 0.0) + penalties.get("ensemble_low", 0.0),
                narrative=self._ensemble_narrative(ensemble),
            )
        )

        return components

    def _memory_narrative(self, memory: MarketMemoryAssessment) -> str:
        if memory.samples == 0:
            return "No historical analogs found for this setup in current context."
        if memory.fragility_score > 0.7:
            return "Historical analogs show fragile outcomes with elevated stop-out density."
        if memory.weighted_expectancy_r > 0.3 and memory.weighted_win_rate > 0.55:
            return "Historical analogs show positive expectancy and stable hit-rate."
        return "Historical analogs are mixed with moderate reliability."

    def _stress_narrative(self, stress: StressReport) -> str:
        if stress.fragile:
            return "Scenario stress profile is fragile with unfavorable left-tail behavior."
        if stress.distribution.p10_r > 0:
            return "Stress paths maintain positive edge across most adverse trajectories."
        return "Stress profile is acceptable but includes manageable downside tails."

    def _alignment_narrative(self, alignment: AlignmentReport) -> str:
        if alignment.htf_veto:
            return "Higher timeframe veto dominates lower timeframe execution bias."
        if alignment.contradiction_severity > 0.6:
            return "Timeframe contradiction is elevated; tactical execution may be noisy."
        return "Timeframes are sufficiently aligned for controlled execution."

    def _portfolio_narrative(self, portfolio: PortfolioGraphReport) -> str:
        if portfolio.concentration_score > 0.7:
            return "Portfolio concentration is high; candidate trade increases correlated risk."
        if portfolio.fragility_score > 0.65:
            return "Cross-position stress graph indicates fragile liquidation clustering."
        return "Portfolio interaction profile remains within diversification tolerances."

    def _session_narrative(self, session: SessionDecision) -> str:
        if session.block_new_risk:
            return "Session/event state blocks new risk until window clears."
        if session.liquidity_penalty > 0.35:
            return "Liquidity conditions are suboptimal and require reduced sizing."
        return "Session context is supportive with manageable transition risk."

    def _feature_narrative(self, feature_report: FeatureGovernanceReport) -> str:
        if feature_report.critical_issues:
            joined = ", ".join(sorted(feature_report.critical_issues)[:3])
            return f"Critical feature issues detected ({joined})."
        if feature_report.quarantined_features:
            return "Non-critical features quarantined due to drift; confidence is reduced."
        return "Feature health is stable and within expected distribution bands."

    def _ensemble_narrative(self, ensemble: EnsembleDecision) -> str:
        if ensemble.inter_family_conflict > 0.65:
            return "Thesis families show elevated directional conflict."
        if ensemble.confidence < 0.25:
            return "Thesis-level consensus confidence is weak."
        return "Thesis families present coherent directional consensus."


class DecisionDiagnostics:
    @staticmethod
    def compute(component_scores: list[DecisionComponentScore], penalties: dict[str, float], final_confidence: float) -> dict[str, float]:
        gross = sum(c.weighted_score for c in component_scores)
        total_penalty = sum(penalties.values())
        net = gross - total_penalty
        dispersion = mean(abs(c.raw_score - mean(cc.raw_score for cc in component_scores)) for c in component_scores) if component_scores else 0.0
        return {
            "gross_score": gross,
            "total_penalty": total_penalty,
            "net_score": net,
            "confidence_error": abs(net - final_confidence),
            "component_dispersion": dispersion,
        }


class DecisionExplainabilityEngine:
    def __init__(self) -> None:
        self.explainer = ReasonCodeExplainer()
        self.builder = DecisionAttributionBuilder()

    def build(
        self,
        *,
        final_confidence: float,
        size_multiplier: float,
        approved: bool,
        reason_codes: list[str],
        penalties: dict[str, float],
        memory: MarketMemoryAssessment,
        stress: StressReport,
        alignment: AlignmentReport,
        portfolio: PortfolioGraphReport,
        session: SessionDecision,
        feature_report: FeatureGovernanceReport,
        ensemble: EnsembleDecision,
    ) -> DecisionExplanation:
        component_scores = self.builder.build(
            memory=memory,
            stress=stress,
            alignment=alignment,
            portfolio=portfolio,
            session=session,
            feature_report=feature_report,
            ensemble=ensemble,
            penalties=penalties,
        )
        reasons = self.explainer.explain(reason_codes)
        diagnostics = DecisionDiagnostics.compute(component_scores, penalties, final_confidence)

        return DecisionExplanation(
            final_confidence=final_confidence,
            size_multiplier=size_multiplier,
            approval=approved,
            component_scores=component_scores,
            reason_code_explanations=reasons,
            diagnostics=diagnostics,
        )


__all__ = [
    "DecisionAttributionBuilder",
    "DecisionComponentScore",
    "DecisionDiagnostics",
    "DecisionExplainabilityEngine",
    "DecisionExplanation",
    "ReasonCodeExplainer",
]
