from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .confidence_calibration import ConfidenceCalibrator
from .decision_reason_tree import DecisionReasonTree
from .edge_threshold_model import EdgeThresholdModel
from .execution_simulator import ExecutionEstimate
from .regime_transition_model import RegimeTransitionState
from .signal_graph import SignalDependencyReport
from .trade_distribution import DecisionOutcome, TradeDistribution


@dataclass(slots=True)
class DecisionEngine:
    confidence: ConfidenceCalibrator
    thresholds: EdgeThresholdModel
    reason_tree: DecisionReasonTree

    def build_distribution(
        self,
        candidate: dict[str, Any],
        execution: ExecutionEstimate,
        signal_report: SignalDependencyReport,
        regime_state: RegimeTransitionState,
        market_context: dict[str, Any],
    ) -> TradeDistribution:
        raw_alpha = float(candidate.get("ev_r", 0.0))
        raw_conf = float(candidate.get("confidence", 0.5))
        staleness = int(market_context.get("signal_staleness_sec", 0))
        calibrated_conf = self.confidence.calibrate(raw_conf, staleness, signal_report.disagreement_score)
        uncertainty = self.confidence.uncertainty(calibrated_conf, float(market_context.get("volatility_score", 0.4)))

        fill_adjusted = raw_alpha - execution.spread_cost - execution.slippage_cost - execution.toxicity_penalty
        expected_return = fill_adjusted * calibrated_conf * signal_report.orthogonal_score
        downside = max(0.0, abs(float(candidate.get("stop_distance_r", 1.0))) * (1.0 - calibrated_conf) + regime_state.transition_risk * 0.3)
        hold_sec = int(candidate.get("target_hold_seconds", 1200))
        interval = (expected_return - uncertainty, expected_return + uncertainty)

        return TradeDistribution(
            expected_return=expected_return,
            expected_downside=downside,
            expected_holding_time_sec=hold_sec,
            fill_adjusted_alpha=fill_adjusted,
            uncertainty=uncertainty,
            confidence=calibrated_conf,
            uncertainty_interval=interval,
            raw_alpha=raw_alpha,
            spread_cost=execution.spread_cost,
            slippage_cost=execution.slippage_cost,
            toxicity_penalty=execution.toxicity_penalty,
        )

    def decide(
        self,
        candidate: dict[str, Any],
        distribution: TradeDistribution,
        execution: ExecutionEstimate,
        signal_report: SignalDependencyReport,
        regime_state: RegimeTransitionState,
        health_block: bool,
        health_cap: float,
        health_reasons: list[str],
        session_name: str,
    ) -> DecisionOutcome:
        reasons = list(signal_report.reason_codes) + list(health_reasons)
        rejections: list[str] = []

        if health_block:
            rejections.append("HEALTH_CIRCUIT_BREAKER")

        min_edge = self.thresholds.min_edge(str(candidate.get("instrument", "")), session_name)
        max_uncertainty = self.thresholds.max_uncertainty(session_name)

        if distribution.fill_adjusted_alpha <= min_edge:
            rejections.append("DECISION_NEGATIVE_EDGE")
        if distribution.expected_downside > float(candidate.get("max_downside_r", 0.85)):
            rejections.append("DECISION_DOWNSIDE_TOO_HIGH")
        if distribution.uncertainty > max_uncertainty:
            rejections.append("DECISION_UNCERTAINTY_TOO_HIGH")
        if execution.execution_quality < float(candidate.get("min_execution_quality", 0.25)):
            rejections.append("DECISION_EXECUTION_QUALITY_LOW")
        if regime_state.transition_risk > float(candidate.get("max_transition_risk", 0.70)):
            rejections.append("DECISION_TRANSITION_RISK_HIGH")

        approved = len(rejections) == 0
        status = "approved"
        size_cap = min(1.0, health_cap)
        if approved and regime_state.unsafe_for_trend:
            size_cap = min(size_cap, 0.75)
            status = "degraded_approved"
            reasons.append("REGIME_UNSAFE_TREND_DERATE")
        if not approved:
            status = "declined"

        decline = self.reason_tree.order_rejections(rejections)
        reasons.extend(decline)

        return DecisionOutcome(
            approved=approved,
            approval_status=status,
            reason_codes=reasons,
            decline_reason_hierarchy=decline,
            min_edge_required=min_edge,
            transition_risk=regime_state.transition_risk,
            execution_quality_estimate=execution.execution_quality,
            size_multiplier_cap=size_cap,
        )


def build_decision_engine() -> DecisionEngine:
    return DecisionEngine(
        confidence=ConfidenceCalibrator(),
        thresholds=EdgeThresholdModel(),
        reason_tree=DecisionReasonTree(),
    )
