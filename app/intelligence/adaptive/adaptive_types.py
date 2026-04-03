from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdaptiveDecision:
    """Top-level adaptive decision payload attached to a snapshot."""

    approved: bool
    confidence_delta: float
    size_delta: float
    reason_codes: list[str] = field(default_factory=list)
    telemetry: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CapitalEfficiencyReport:
    capital_efficiency_score: float
    expected_edge: float
    incremental_margin: float
    free_margin_after_fill: float
    margin_headroom_ratio: float
    liquidation_cascade_risk: float
    opportunity_cost_penalty: float
    lockup_by_family: dict[str, float] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ThesisLeg:
    thesis_id: str
    weight: float
    confidence: float
    expected_contribution: float
    invalidation_rule: str


@dataclass(frozen=True)
class ThesisVector:
    legs: list[ThesisLeg] = field(default_factory=list)
    dominant_thesis: str = "none"
    fragility_score: float = 0.0
    decay_score: float = 0.0
    expectancy_score: float = 0.0


@dataclass(frozen=True)
class NegotiationObjection:
    source_engine: str
    objection_type: str
    severity: float
    message: str
    hard_veto: bool = False


@dataclass(frozen=True)
class NegotiationOutcome:
    blocked: bool
    total_penalty: float
    veto_sources: list[str] = field(default_factory=list)
    objections: list[NegotiationObjection] = field(default_factory=list)
    dispute_trace: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PathDependencyReport:
    health_label: str
    path_quality_score: float
    confidence_decay: float
    stop_tightening_factor: float
    scale_out_bias: float
    near_invalidation_ratio: float
    followthrough_score: float


@dataclass(frozen=True)
class RetryDecision:
    allow_retry: bool
    retry_size_multiplier: float
    fatigue_score: float
    threshold_increase: float
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EdgePersistenceReport:
    half_life_bars: float
    persistence_score: float
    expectancy_slope: float
    saturation_score: float
    crowding_penalty: float
    overheating_flag: bool
    trust_multiplier: float


@dataclass(frozen=True)
class AdversaryReport:
    fragility_score: float
    survives_review: bool
    top_failure_modes: list[str] = field(default_factory=list)
    defensive_adjustments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionMemoryReport:
    recommended_order_style: str
    expected_slippage_bps: float
    passive_fill_quality: float
    aggressive_fill_quality: float
    cancel_success_rate: float
    tactic_penalty: float


@dataclass(frozen=True)
class DecisionNarrative:
    summary: str
    support_factors: list[str] = field(default_factory=list)
    opposition_factors: list[str] = field(default_factory=list)
    penalty_breakdown: dict[str, float] = field(default_factory=dict)
    invalidation_triggers: list[str] = field(default_factory=list)
    execution_rationale: str = ""
    json_report: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SandboxEvaluation:
    paper_mode_only: bool
    candidate_module: str
    score: float
    promotion_ready: bool
    promotion_reasons: list[str] = field(default_factory=list)
