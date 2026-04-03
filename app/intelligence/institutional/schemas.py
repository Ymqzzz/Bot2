from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ReasonCode(str, Enum):
    MEMORY_SETUP_FRAGILE = "memory_setup_fragile"
    MEMORY_INSUFFICIENT_HISTORY = "memory_insufficient_history"
    STRESS_ROBUSTNESS_LOW = "stress_robustness_low"
    STRESS_WORST_CASE_EXCESSIVE = "stress_worst_case_excessive"
    TIMEFRAME_CONFLICT = "timeframe_conflict"
    TIMEFRAME_HTF_VETO = "timeframe_htf_veto"
    PORTFOLIO_CONCENTRATION = "portfolio_concentration"
    PORTFOLIO_CLUSTER_FRAGILITY = "portfolio_cluster_fragility"
    SESSION_RISK_WINDOW = "session_risk_window"
    SESSION_LOW_LIQUIDITY = "session_low_liquidity"
    FEATURE_DRIFT = "feature_drift"
    FEATURE_MISSING_CRITICAL = "feature_missing_critical"
    FEATURE_INSTABILITY = "feature_instability"
    ENSEMBLE_DIRECTION_CONFLICT = "ensemble_direction_conflict"
    ENSEMBLE_LOW_CONSENSUS = "ensemble_low_consensus"
    LIFECYCLE_THESIS_INVALIDATED = "lifecycle_thesis_invalidated"
    LIFECYCLE_TIME_DECAY = "lifecycle_time_decay"
    LIFECYCLE_EVENT_EXIT = "lifecycle_event_exit"


@dataclass(frozen=True)
class Evidence:
    code: str
    weight: float
    value: float
    detail: str


@dataclass(frozen=True)
class SetupRecord:
    record_id: str
    setup_type: str
    regime: str
    session: str
    instrument: str
    direction: Direction
    compression_score: float
    volatility_state: str
    post_news_state: str
    microstructure_tag: str
    entry_quality: float
    pnl_r: float
    mfe_r: float
    mae_r: float
    stop_out: bool
    holding_bars: int
    created_at: datetime


@dataclass(frozen=True)
class MemoryQuery:
    setup_type: str
    regime: str
    session: str
    instrument: str
    direction: Direction
    compression_score: float
    volatility_state: str
    post_news_state: str
    microstructure_tag: str


@dataclass(frozen=True)
class SimilarSetup:
    record_id: str
    similarity: float
    pnl_r: float
    stop_out: bool
    holding_bars: int
    regime: str
    session: str


@dataclass(frozen=True)
class FailureCluster:
    cluster_id: str
    label: str
    frequency: float
    avg_loss_r: float
    dominant_regime: str
    dominant_session: str


@dataclass(frozen=True)
class MarketMemoryAssessment:
    samples: int
    weighted_win_rate: float
    weighted_expectancy_r: float
    weighted_stop_out_rate: float
    weighted_mfe_r: float
    weighted_mae_r: float
    mean_holding_bars: float
    fragility_score: float
    confidence: float
    failure_clusters: list[FailureCluster] = field(default_factory=list)
    top_matches: list[SimilarSetup] = field(default_factory=list)


@dataclass(frozen=True)
class TradeProposal:
    trade_id: str
    instrument: str
    side: Direction
    entry: float
    stop: float
    target: float
    quantity: float
    setup_type: str
    regime: str
    session: str
    strategy: str
    thesis_family: str
    expected_holding_bars: int
    features: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioPath:
    scenario_name: str
    vol_multiplier: float
    spread_multiplier: float
    slippage_bps: float
    fill_delay_bars: int
    partial_fill_ratio: float
    shock_direction: Direction
    correlated_shock: float
    liquidity_gap: float


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario_name: str
    pnl_r: float
    max_drawdown_r: float
    fill_quality: float
    break_probability: float


@dataclass(frozen=True)
class StressDistribution:
    outcomes: list[ScenarioOutcome]
    expected_r: float
    median_r: float
    p10_r: float
    p5_r: float
    worst_r: float
    drawdown_p95: float


@dataclass(frozen=True)
class StressReport:
    path_count: int
    robustness_score: float
    fragility_score: float
    fragile: bool
    distribution: StressDistribution
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TimeframeState:
    timeframe: str
    direction: Direction
    confidence: float
    trend_score: float
    structure_score: float
    volatility_score: float


@dataclass(frozen=True)
class TimeframeContribution:
    timeframe: str
    weight: float
    directional_value: float
    confidence: float


@dataclass(frozen=True)
class AlignmentReport:
    alignment_score: float
    contradiction_severity: float
    htf_veto: bool
    veto: bool
    refinement_bias: Direction
    contributions: list[TimeframeContribution] = field(default_factory=list)


@dataclass(frozen=True)
class PositionNode:
    position_id: str
    instrument: str
    thesis_family: str
    quantity: float
    notional: float
    beta_risk_on: float
    usd_beta: float
    rates_beta: float
    commodities_beta: float
    stop_distance_r: float
    regime_tag: str
    event_vulnerability: float


@dataclass(frozen=True)
class InteractionEdge:
    src_position_id: str
    dst_position_id: str
    same_thesis_score: float
    factor_overlap_score: float
    stop_overlap_score: float
    liquidation_correlation: float


@dataclass(frozen=True)
class PortfolioGraphReport:
    node_count: int
    edge_count: int
    concentration_score: float
    same_thesis_ratio: float
    factor_crowding_score: float
    stop_overlap_score: float
    fragility_score: float
    netting_suggestions: list[str] = field(default_factory=list)
    edges: list[InteractionEdge] = field(default_factory=list)


class PositionState(str, Enum):
    PROPOSED = "proposed"
    STAGED = "staged"
    PARTIALLY_FILLED = "partially_filled"
    ACTIVE = "active"
    REDUCED = "reduced"
    HEDGED = "hedged"
    TRAILING = "trailing"
    TIME_DECAY_WATCH = "time_decay_watch"
    EMERGENCY_EXIT_CANDIDATE = "emergency_exit_candidate"
    CLOSED = "closed"
    POSTMORTEM_PENDING = "postmortem_pending"


@dataclass
class LifecycleSnapshot:
    trade_id: str
    state: PositionState
    confidence: float
    bars_open: int
    fill_ratio: float
    avg_entry_price: float
    current_price: float
    stop_price: float
    target_price: float
    realized_r: float
    unrealized_r: float
    max_favorable_excursion_r: float
    max_adverse_excursion_r: float
    thesis_score: float
    event_risk_score: float
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LifecycleTransition:
    trade_id: str
    from_state: PositionState
    to_state: PositionState
    reason: str
    timestamp: datetime


@dataclass(frozen=True)
class SessionProfile:
    name: str
    edge_threshold_multiplier: float
    size_multiplier: float
    liquidity_score: float
    volatility_spike_risk: float


@dataclass(frozen=True)
class EventWindow:
    label: str
    start: datetime
    end: datetime
    severity: float
    relevance: float


@dataclass(frozen=True)
class SessionDecision:
    active_session: str
    edge_multiplier: float
    size_multiplier: float
    block_new_risk: bool
    transition_risk: float
    liquidity_penalty: float


@dataclass(frozen=True)
class FeatureReference:
    feature: str
    mean: float
    std: float
    lower: float
    upper: float
    critical: bool


@dataclass(frozen=True)
class FeatureHealth:
    feature: str
    missingness: float
    drift_score: float
    stability_score: float
    saturation_score: float
    redundancy_score: float
    quarantined: bool
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeatureGovernanceReport:
    overall_health: float
    quarantined_features: list[str]
    critical_issues: list[str]
    by_feature: dict[str, FeatureHealth]


@dataclass(frozen=True)
class ModelVersion:
    model_name: str
    version: str
    training_data_tag: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionSnapshot:
    decision_id: str
    timestamp: datetime
    trade_id: str
    model_versions: dict[str, str]
    feature_hash: str
    regime_snapshot: dict[str, Any]
    signal_contributors: dict[str, float]
    penalties: dict[str, float]
    overrides: dict[str, str]
    reason_codes: list[str]
    approval_path: list[str]
    approved: bool
    confidence: float


@dataclass(frozen=True)
class ThesisVote:
    source: str
    thesis_family: str
    direction: Direction
    confidence: float
    weight: float


@dataclass(frozen=True)
class FamilyConsensus:
    thesis_family: str
    net_direction: Direction
    confidence: float
    disagreement: float
    voters: int


@dataclass(frozen=True)
class EnsembleDecision:
    net_direction: Direction
    confidence: float
    inter_family_conflict: float
    family_consensus: list[FamilyConsensus]


@dataclass(frozen=True)
class TelemetryEvent:
    source: str
    heartbeat_ts: datetime
    confidence: float
    latency_ms: float
    health: HealthState
    payload: dict[str, Any]


@dataclass(frozen=True)
class AlertEvent:
    alert_id: str
    source: str
    severity: str
    message: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpsSnapshot:
    generated_at: datetime
    health_ratio: float
    avg_confidence: float
    avg_latency_ms: float
    degraded_sources: list[str]
    active_alerts: list[AlertEvent]


@dataclass(frozen=True)
class InstitutionalDecision:
    approved: bool
    confidence: float
    size_multiplier: float
    reason_codes: list[str]
    memory: MarketMemoryAssessment
    stress: StressReport
    alignment: AlignmentReport
    portfolio: PortfolioGraphReport
    session: SessionDecision
    feature_governance: FeatureGovernanceReport
    ensemble: EnsembleDecision


def to_dict(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: to_dict(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return to_dict(asdict(value))
    return value


__all__ = [
    "AlertEvent",
    "AlignmentReport",
    "DecisionSnapshot",
    "Direction",
    "EnsembleDecision",
    "EventWindow",
    "Evidence",
    "FailureCluster",
    "FamilyConsensus",
    "FeatureGovernanceReport",
    "FeatureHealth",
    "FeatureReference",
    "HealthState",
    "InstitutionalDecision",
    "InteractionEdge",
    "LifecycleSnapshot",
    "LifecycleTransition",
    "MarketMemoryAssessment",
    "MemoryQuery",
    "ModelVersion",
    "OpsSnapshot",
    "PortfolioGraphReport",
    "PositionNode",
    "PositionState",
    "ReasonCode",
    "ScenarioOutcome",
    "ScenarioPath",
    "SessionDecision",
    "SessionProfile",
    "SetupRecord",
    "SimilarSetup",
    "StressDistribution",
    "StressReport",
    "ThesisVote",
    "TimeframeContribution",
    "TimeframeState",
    "TradeProposal",
    "TelemetryEvent",
    "to_dict",
]
