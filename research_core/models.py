from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ReplayStepRecord:
    step_ts: datetime
    instrument: str
    market_intel_ref: str | None
    trade_intel_ref: str | None
    control_plane_ref: str | None
    candidate_ids: list[str]
    approved_candidate_ids: list[str]
    blocked_candidate_ids: list[str]
    meta_decision_ids: list[str]
    execution_outcomes: list[dict[str, Any]]
    open_positions_snapshot: dict[str, Any]
    portfolio_state_snapshot: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "step_ts": self.step_ts.isoformat(),
        }


@dataclass(slots=True)
class ReplayResult:
    replay_id: str
    start_ts: datetime
    end_ts: datetime
    instruments: list[str]
    num_steps: int
    num_candidates: int
    num_approved: int
    num_rejected: int
    num_executed: int
    num_closed_trades: int
    gross_pnl: float
    net_pnl: float
    net_r: float
    max_drawdown_r: float
    approval_rate: float
    step_records: list[ReplayStepRecord]
    divergence_flags: list[str]
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["start_ts"] = self.start_ts.isoformat()
        payload["end_ts"] = self.end_ts.isoformat()
        payload["step_records"] = [record.to_flat_dict() for record in self.step_records]
        return payload


@dataclass(slots=True)
class ScenarioDefinition:
    scenario_id: str
    name: str
    description: str
    parameter_overrides: dict[str, object]
    feature_toggles: dict[str, bool]
    policy_overrides: dict[str, object]
    notes: str | None = None

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SimulationRun:
    simulation_id: str
    baseline_scenario: ScenarioDefinition
    variant_scenarios: list[ScenarioDefinition]
    start_ts: datetime
    end_ts: datetime
    results_by_scenario: dict[str, dict[str, Any]]
    comparisons: dict[str, dict[str, Any]]
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "baseline_scenario": self.baseline_scenario.to_flat_dict(),
            "variant_scenarios": [s.to_flat_dict() for s in self.variant_scenarios],
            "start_ts": self.start_ts.isoformat(),
            "end_ts": self.end_ts.isoformat(),
            "results_by_scenario": self.results_by_scenario,
            "comparisons": self.comparisons,
            "reason_codes": self.reason_codes,
        }


@dataclass(slots=True)
class CalibrationBin:
    bin_id: str
    score_min: float
    score_max: float
    count: int
    avg_raw_score: float
    empirical_win_rate: float | None
    empirical_expectancy_r: float | None
    avg_mfe_r: float | None
    avg_mae_r: float | None
    brier_component: float | None
    ece_component: float | None


@dataclass(slots=True)
class CalibrationSnapshot:
    calibration_id: str
    scope_type: str
    scope_key: str
    sample_size: int
    calibration_method: str
    reliability_score: float
    brier_score: float | None
    ece_score: float | None
    mce_score: float | None
    bins: list[CalibrationBin]
    mapping_params: dict[str, float | str]
    fresh_asof: datetime
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fresh_asof"] = self.fresh_asof.isoformat()
        return payload


@dataclass(slots=True)
class MetaApprovalDecision:
    decision_id: str
    candidate_id: str
    instrument: str
    strategy_name: str
    action: str
    approval_score: float
    calibrated_win_prob: float | None
    calibrated_expectancy_proxy: float | None
    risk_adjustment_multiplier: float
    delay_seconds: int | None
    reject: bool
    reject_hard: bool
    reason_codes: list[str]
    diagnostics: dict[str, float | str | bool | None]

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MetaFeatureSnapshot:
    candidate_id: str
    instrument: str
    strategy_name: str
    setup_type: str
    raw_confidence: float
    raw_expected_value: float
    market_intel_quality: float | None
    entry_precision_score: float | None
    execution_feasibility_score: float | None
    regime_support_score: float | None
    event_support_score: float | None
    portfolio_fit_score: float | None
    edge_score: float | None
    calibrated_win_prob: float | None
    calibrated_expectancy_proxy: float | None
    recent_false_break_rate: float | None
    recent_timing_loss_rate: float | None
    recent_execution_loss_rate: float | None
    late_entry_risk: float | None
    spread_dislocation_risk: float | None
    escape_risk_score: float | None
    meta_quality_score: float
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExperimentComparison:
    baseline_scenario_id: str
    variant_scenario_id: str
    net_r_delta: float
    approval_rate_delta: float
    win_rate_delta: float | None
    profit_factor_delta: float | None
    avg_slippage_delta_bps: float | None
    drawdown_delta_r: float | None
    avg_entry_quality_delta: float | None
    avg_exit_quality_delta: float | None
    reason_codes: list[str]

    def to_flat_dict(self) -> dict[str, Any]:
        return asdict(self)
