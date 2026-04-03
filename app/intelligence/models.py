from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1.1.0"


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class Evidence:
    code: str
    weight: float
    value: float
    note: str


@dataclass(frozen=True)
class IntelligenceState:
    timestamp: datetime
    instrument: str
    trace_id: str
    schema_version: str = SCHEMA_VERSION
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    rationale: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class RegimeState(IntelligenceState):
    label: str = "unknown"
    score_vector: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TimeframeBias:
    timeframe: str
    direction: Direction
    confidence: float
    trend_quality: float
    structure_quality: float
    momentum_quality: float


@dataclass(frozen=True)
class MultiTimeframeBiasState(IntelligenceState):
    frame_bias: list[TimeframeBias] = field(default_factory=list)
    htf_bias: Direction = Direction.NEUTRAL
    setup_bias: Direction = Direction.NEUTRAL
    trigger_bias: Direction = Direction.NEUTRAL
    alignment_score: float = 0.0
    conflict_score: float = 0.0
    alignment_label: str = "neutral"


@dataclass(frozen=True)
class StructureEvent:
    event_type: str
    direction: Direction
    strength: float
    level: float


@dataclass(frozen=True)
class StructureState(IntelligenceState):
    structure_label: str = "mixed"
    trend_direction: Direction = Direction.NEUTRAL
    displacement_strength: float = 0.0
    cleanliness_score: float = 0.0
    support_resistance: dict[str, list[float]] = field(default_factory=dict)
    events: list[StructureEvent] = field(default_factory=list)
    current_phase: str = "unknown"
    phase_confidence: float = 0.0
    recent_phase_transition: str = "none"
    structural_narrative: str = "insufficient_structure"
    current_phase: str = "range_rotation"
    phase_confidence: float = 0.0
    recent_phase_transition: str = "none"
    structural_narrative: str = ""
    continuation_quality_score: float = 0.0
    reversal_quality_score: float = 0.0
    compression_score: float = 0.0
    reclaim_score: float = 0.0
    messiness_penalty: float = 0.0


@dataclass(frozen=True)
class LiquidityZone:
    pool_id: str
    pool_type: str
    level: float
    distance: float
    significance: float
    price_level: float
    distance_from_current_price: float
    significance_score: float
    visibility_score: float = 0.0
    cluster_density_score: float = 0.0
    recency_score: float = 0.0
    touch_count: int = 0
    sweep_risk_score: float = 0.0
    target_likelihood_score: float = 0.0


@dataclass(frozen=True)
class LiquidityState(IntelligenceState):
    pressure_score: float = 0.0
    target_hypothesis: str = "none"
    nearest_zones: list[LiquidityZone] = field(default_factory=list)
    nearest_upside_pool: str = "none"
    nearest_downside_pool: str = "none"
    most_significant_pool: str = "none"
    current_liquidity_target_hypothesis: str = "none"
    liquidity_pressure_direction: str = "neutral"
    liquidity_context_label: str = "neutral"
    nearest_upside_pool: str = ""
    nearest_downside_pool: str = ""
    most_significant_pool: str = ""
    current_liquidity_target_hypothesis: str = "none"
    liquidity_pressure_direction: str = "neutral"
    liquidity_context_label: str = "unclear"
    all_pools: list[LiquidityZone] = field(default_factory=list)


@dataclass(frozen=True)
class SweepState(IntelligenceState):
    sweep_detected: bool = False
    sweep_type: str = "none"
    interpretation: str = "none"
    reversal_probability: float = 0.0
    continuation_probability: float = 0.0
    rejection_strength: float = 0.0
    breached_pool_id: str | None = None
    breached_pool_id: str = ""
    breach_depth: float = 0.0
    acceptance_strength: float = 0.0
    follow_through_score: float = 0.0
    post_sweep_state: str = "none"
    sweep_confidence: float = 0.0


@dataclass(frozen=True)
class EventRiskState(IntelligenceState):
    event_label: str = "no_event"
    severity_score: float = 0.0
    contamination_score: float = 0.0
    pre_event_suppression: bool = False
    post_event_instability: float = 0.0
    cooldown_state: str = "inactive"


@dataclass(frozen=True)
class InstrumentHealthState(IntelligenceState):
    health_score: float = 1.0
    health_label: str = "healthy"
    tradable: bool = True
    penalty_multiplier: float = 1.0


@dataclass(frozen=True)
class StrategyHealthState(IntelligenceState):
    strategy_scores: dict[str, float] = field(default_factory=dict)
    strategy_labels: dict[str, str] = field(default_factory=dict)
    throttle_multipliers: dict[str, float] = field(default_factory=dict)
    disable_flags: dict[str, bool] = field(default_factory=dict)
    sample_quality_scores: dict[str, float] = field(default_factory=dict)
    rank_penalties: dict[str, float] = field(default_factory=dict)
    size_penalties: dict[str, float] = field(default_factory=dict)
    health_details: dict[str, dict[str, float | str | bool]] = field(default_factory=dict)


@dataclass(frozen=True)
class CrossAssetContextState(IntelligenceState):
    usd_alignment_score: float = 0.0
    macro_support_score: float = 0.0
    risk_sentiment_score: float = 0.0
    divergence_score: float = 0.0
    confirmation_label: str = "missing"


@dataclass(frozen=True)
class TradeQualityState(IntelligenceState):
    quality_score: float = 0.0
    approval_confidence: float = 0.0
    cleanliness_score: float = 0.0
    uncertainty_score: float = 1.0
    quality_label: str = "low"
    size_multiplier: float = 0.5
    contributions: dict[str, float] = field(default_factory=dict)
    alignment_score: float = 0.0
    context_penalty_score: float = 0.0
    execution_burden_score: float = 0.0
    size_multiplier_hint: float = 0.5
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    trade_quality_score: float = 0.0
    setup_cleanliness_score: float = 0.0
    alignment_score: float = 0.0
    context_penalty_score: float = 0.0
    execution_burden_score: float = 0.0
    size_multiplier_hint: float = 0.0
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UncertaintyState(IntelligenceState):
    uncertainty_score: float = 0.0
    uncertainty_label: str = "low"
    uncertainty_drivers: dict[str, float] = field(default_factory=dict)
    confidence_adjustment: float = 0.0
    size_penalty_multiplier: float = 1.0
    ranking_penalty: float = 0.0
    block_if_extreme_flag: bool = False


@dataclass(frozen=True)
class AnalogSimilarityState(IntelligenceState):
    similarity_score: float = 0.0
    comparable_cases: int = 0
    avg_outcome: float = 0.0
    outcome_dispersion: float = 0.0
    best_strategy_family: str = "unknown"
    analog_confidence: float = 0.0
    matched_case_count: int = 0
    top_match_count_used: int = 0
    historical_expectancy: float = 0.0
    historical_win_rate: float = 0.0
    historical_payoff_ratio: float = 0.0
    historical_mae_median: float = 0.0
    historical_mfe_median: float = 0.0
    insufficient_history_flag: bool = False


@dataclass(frozen=True)
class UncertaintyState(IntelligenceState):
    uncertainty_score: float = 0.0
    uncertainty_label: str = "low"
    uncertainty_drivers: dict[str, float] = field(default_factory=dict)
    confidence_adjustment: float = 0.0
    size_penalty_multiplier: float = 1.0
    ranking_penalty: float = 0.0
    block_if_extreme_flag: bool = False


@dataclass(frozen=True)
class ConfidenceCalibrationState(IntelligenceState):
    raw_confidence: float = 0.0
    calibrated_confidence: float = 0.0
    calibration_bucket: str = "neutral"
    delta: float = 0.0


@dataclass(frozen=True)
class AdaptiveIntelligenceState(IntelligenceState):
    capital_efficiency: dict[str, Any] = field(default_factory=dict)
    thesis_vector: dict[str, Any] = field(default_factory=dict)
    negotiation: dict[str, Any] = field(default_factory=dict)
    path_dependency: dict[str, Any] = field(default_factory=dict)
    retry: dict[str, Any] = field(default_factory=dict)
    edge_persistence: dict[str, Any] = field(default_factory=dict)
    adversary: dict[str, Any] = field(default_factory=dict)
    execution_memory: dict[str, Any] = field(default_factory=dict)
    decision_narrative: dict[str, Any] = field(default_factory=dict)
    sandbox: dict[str, Any] = field(default_factory=dict)
    adaptive_approval: bool = False
    adaptive_confidence_delta: float = 0.0
    adaptive_size_delta: float = 0.0
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarketIntelligenceSnapshot(IntelligenceState):
    regime: RegimeState | None = None
    mtf_bias: MultiTimeframeBiasState | None = None
    structure: StructureState | None = None
    liquidity: LiquidityState | None = None
    sweep: SweepState | None = None
    event_risk: EventRiskState | None = None
    instrument_health: InstrumentHealthState | None = None
    strategy_health: StrategyHealthState | None = None
    cross_asset: CrossAssetContextState | None = None
    trade_quality: TradeQualityState | None = None
    uncertainty: UncertaintyState | None = None
    analog: AnalogSimilarityState | None = None
    calibration: ConfidenceCalibrationState | None = None
    adaptive: AdaptiveIntelligenceState | None = None
    integrity_flags: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))
