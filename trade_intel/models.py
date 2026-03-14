from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TradeFingerprint:
    trade_id: str
    instrument: str
    strategy_name: str
    setup_type: str
    subtype: str | None
    decision_ts: datetime
    entry_ts: datetime | None
    side: str
    entry_planned: float
    entry_filled: float | None
    stop_initial: float
    target_initial: float
    order_type: str
    confidence_raw: float
    expected_value_raw: float
    rr_planned: float
    intel_quality_score: float | None
    entry_precision_score: float | None
    execution_feasibility_score: float | None
    liquidity_event_risk_score: float | None
    market_state_quality_score: float | None
    session_name: str
    regime_name: str
    spread_regime: str
    gamma_mode: str | None
    volume_profile_state: str | None
    cross_asset_state: str | None
    sizing_reason_codes: list[str] = field(default_factory=list)
    approval_reason_codes: list[str] = field(default_factory=list)
    snapshot_ref: str | None = None

    def to_flat_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["decision_ts"] = self.decision_ts.isoformat()
        out["entry_ts"] = self.entry_ts.isoformat() if self.entry_ts else None
        return out


@dataclass(slots=True)
class EntryQualityAssessment:
    entry_quality_label: str
    entry_quality_score: float
    was_late: bool
    was_early: bool
    was_chased: bool
    was_passive_improvement: bool
    filled_near_optimal_zone: bool
    distance_from_structural_level_bps: float | None
    distance_from_profile_level_bps: float | None
    slippage_bps: float | None
    spread_at_entry_bps: float | None
    adverse_selection_score: float
    entry_reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradePathMetrics:
    trade_id: str
    bars_held: int
    seconds_held: int
    mfe_pips: float
    mae_pips: float
    mfe_r: float
    mae_r: float
    peak_unrealized_pnl: float
    worst_unrealized_pnl: float
    time_to_mfe_sec: int | None
    time_to_mae_sec: int | None
    time_to_first_positive_sec: int | None
    time_to_first_negative_sec: int | None
    max_heat_fraction: float
    volatility_during_hold_score: float
    spread_during_hold_score: float
    execution_stress_during_hold_score: float

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExitQualityAssessment:
    exit_quality_label: str
    exit_quality_score: float
    exit_reason_primary: str
    exit_reason_secondary: str | None
    exit_at_structure: bool
    exit_at_profile_level: bool
    exit_due_to_time_stop: bool
    exit_due_to_trailing: bool
    exit_due_to_regime_change: bool
    exit_due_to_execution_dislocation: bool
    captured_mfe_fraction: float | None
    gave_back_from_peak_fraction: float | None
    exit_reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradeOutcomeAttribution:
    trade_id: str
    outcome_label: str
    outcome_score: float
    driver_primary: str
    driver_secondary: str | None
    contributing_factors: list[str]
    failure_factors: list[str]
    success_factors: list[str]
    environment_bucket: str
    setup_bucket: str
    was_structural_win: bool
    was_execution_loss: bool
    was_timing_loss: bool
    was_regime_mismatch_loss: bool
    was_spread_loss: bool
    was_slippage_loss: bool
    was_exit_mismanagement_loss: bool
    was_thesis_invalidated_fast: bool

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SizingDecision:
    trade_id: str | None
    instrument: str
    strategy_name: str
    base_risk_fraction: float
    recommended_risk_fraction: float
    size_multiplier_total: float
    size_multiplier_intel: float
    size_multiplier_execution: float
    size_multiplier_regime: float
    size_multiplier_edge_health: float
    size_multiplier_session: float
    size_multiplier_portfolio: float
    size_multiplier_recent_performance: float
    hard_cap_applied: bool
    soft_cap_applied: bool
    block_trade: bool
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExitPlan:
    trade_id: str
    exit_plan_type: str
    initial_tp_levels: list[float]
    initial_partial_schedule: list[dict[str, float | str]]
    break_even_arming_rule: str
    trailing_rule: str
    time_stop_rule: str
    regime_invalidation_rule: str
    execution_invalidation_rule: str
    max_hold_seconds: int | None
    reason_codes: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EdgeHealthSnapshot:
    scope_type: str
    scope_key: str
    sample_size: int
    win_rate: float | None
    expectancy_r: float | None
    profit_factor: float | None
    avg_mfe_r: float | None
    avg_mae_r: float | None
    avg_slippage_bps: float | None
    timing_loss_rate: float | None
    execution_loss_rate: float | None
    fast_invalidation_rate: float | None
    rolling_drawdown_r: float | None
    edge_score: float
    edge_state: str
    throttle_multiplier: float
    disable_recommended: bool
    reason_codes: list[str]
    asof: datetime

    def to_flat_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["asof"] = self.asof.isoformat()
        return out


@dataclass(slots=True)
class TradeLifecycleRecord:
    fingerprint: TradeFingerprint
    entry_quality: EntryQualityAssessment | None
    path_metrics: TradePathMetrics | None
    exit_quality: ExitQualityAssessment | None
    attribution: TradeOutcomeAttribution | None
    sizing: SizingDecision | None
    exit_plan: ExitPlan | None
    status: str
    opened_ts: datetime | None
    closed_ts: datetime | None
    realized_pnl: float | None
    realized_r: float | None

    def to_flat_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "opened_ts": self.opened_ts.isoformat() if self.opened_ts else None,
            "closed_ts": self.closed_ts.isoformat() if self.closed_ts else None,
            "realized_pnl": self.realized_pnl,
            "realized_r": self.realized_r,
        }
        out.update({f"fingerprint_{k}": v for k, v in self.fingerprint.to_flat_dict().items()})
        if self.entry_quality:
            out.update({f"entry_{k}": v for k, v in self.entry_quality.to_flat_dict().items()})
        if self.path_metrics:
            out.update({f"path_{k}": v for k, v in self.path_metrics.to_flat_dict().items()})
        if self.exit_quality:
            out.update({f"exit_{k}": v for k, v in self.exit_quality.to_flat_dict().items()})
        if self.attribution:
            out.update({f"attr_{k}": v for k, v in self.attribution.to_flat_dict().items()})
        if self.sizing:
            out.update({f"size_{k}": v for k, v in self.sizing.to_flat_dict().items()})
        if self.exit_plan:
            out.update({f"plan_{k}": v for k, v in self.exit_plan.to_flat_dict().items()})
        return out
