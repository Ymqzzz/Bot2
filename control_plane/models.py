from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def _flat_dict(obj: Any) -> dict[str, Any]:
    out = asdict(obj)
    for key, value in list(out.items()):
        if isinstance(value, datetime):
            out[key] = value.isoformat()
    return out
def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "to_flat_dict"):
        return value.to_flat_dict()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


@dataclass
class RegimeDecision:
    instrument: str
    asof: datetime
    regime_name: str
    regime_confidence: float
    regime_state_label: str
    trend_strength_score: float
    rotation_score: float
    compression_score: float
    expansion_score: float
    event_chaos_score: float
    dead_zone_score: float
    allowed_strategies: list[str]
    suppressed_strategies: list[str]
    blocked_strategies: list[str]
    strategy_weight_multipliers: dict[str, float]
    sizing_cap_multiplier: float
    order_preference: str
    exit_posture: str
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class EventDecision:
    asof: datetime
    event_state: str
    event_phase: str
    active_events: list[dict[str, str | float | int]]
    minutes_to_next_high_impact: int | None
    minutes_since_last_high_impact: int | None
    pre_event_lockout: bool
    post_event_digestion: bool
    spread_normalized: bool
    allow_breakout: bool
    allow_mean_reversion: bool
    allow_sweep_reversal: bool
    allow_trend_pullback: bool
    event_risk_multiplier: float
    execution_penalty_multiplier: float
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class ExecutionDecision:
    trade_id: str | None
    instrument: str
    recommended_tactic: str
    secondary_tactic: str | None
    allow_entry: bool
    fill_probability_score: float
    expected_slippage_bps: float
    adverse_selection_risk: float
    late_entry_risk: float
    spread_dislocation_risk: float
    escape_risk_score: float
    reprice_allowed: bool
    retry_allowed: bool
    max_retries: int
    cancel_if_not_filled_seconds: int | None
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class AllocationCandidate:
    candidate_id: str
    instrument: str
    strategy_name: str
    side: str
    setup_type: str
    expected_value: float
    confidence: float
    risk_fraction_requested: float
    risk_fraction_capped: float | None
    regime_score: float
    event_score: float
    execution_score: float
    edge_score: float
    portfolio_fit_score: float | None
    macro_cluster_key: str | None
    currency_exposure_map: dict[str, float]
    correlation_bucket: str | None
    priority_score: float | None
    blocked: bool
    block_reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
    block_reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class AllocationDecision:
    asof: datetime
    approved_candidate_ids: list[str]
    blocked_candidate_ids: list[str]
    resized_candidate_ids: list[str]
    final_risk_allocations: dict[str, float]
    portfolio_heat_before: float
    portfolio_heat_after: float
    usd_net_exposure_before: float
    usd_net_exposure_after: float
    macro_cluster_allocations: dict[str, float]
    correlation_penalties: dict[str, float]
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class PortfolioStateSnapshot:
    asof: datetime
    open_positions: list[dict]
    instrument_weights: dict[str, float]
    currency_net_exposure: dict[str, float]
    currency_gross_exposure: dict[str, float]
    macro_cluster_exposure: dict[str, float]
    portfolio_heat: float
    correlation_matrix: dict[str, dict[str, float]]
    drawdown_state: str
    risk_budget_remaining: float

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
        return _serialize(asdict(self))


@dataclass
class OrderTacticPlan:
    candidate_id: str
    instrument: str
    tactic_type: str
    entry_style: str
    entry_price: float | None
    limit_offset_bps: float | None
    stop_offset_bps: float | None
    aggression_level: str
    staging_enabled: bool
    num_clips: int
    clip_schedule_seconds: list[int]
    cancel_after_seconds: int | None
    fallback_to_market: bool
    fallback_conditions: list[str]
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return _flat_dict(self)
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass
class ControlPlaneSnapshot:
    asof: datetime
    regime_decisions: dict[str, RegimeDecision]
    event_decision: EventDecision
    execution_decisions: dict[str, ExecutionDecision]
    allocation_decision: AllocationDecision | None
    portfolio_state: PortfolioStateSnapshot
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "asof": self.asof.isoformat(),
            "regime_decisions": {k: v.to_flat_dict() for k, v in self.regime_decisions.items()},
            "event_decision": self.event_decision.to_flat_dict(),
            "execution_decisions": {k: v.to_flat_dict() for k, v in self.execution_decisions.items()},
            "allocation_decision": self.allocation_decision.to_flat_dict() if self.allocation_decision else None,
            "portfolio_state": self.portfolio_state.to_flat_dict(),
            "reason_codes": self.reason_codes,
        }
        data = asdict(self)
        return _serialize(data)
