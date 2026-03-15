from __future__ import annotations

import copy

from research_core.models import ExperimentComparison, ScenarioDefinition


class Simulator:
    def __init__(self, replay_lab):
        self.replay_lab = replay_lab

    def run_baseline(self, replay_inputs) -> dict:
        return copy.deepcopy(replay_inputs)

    def run_variant(self, replay_inputs, scenario: ScenarioDefinition) -> dict:
        variant = copy.deepcopy(replay_inputs)
        variant["scenario_id"] = scenario.scenario_id
        variant["parameter_overrides"] = scenario.parameter_overrides
        variant["policy_overrides"] = scenario.policy_overrides
        variant["feature_toggles"] = scenario.feature_toggles
        return variant

    def compare_runs(self, baseline, variant) -> ExperimentComparison:
        return ExperimentComparison(
            baseline_scenario_id=str(baseline.get("scenario_id", "baseline")),
            variant_scenario_id=str(variant.get("scenario_id", "variant")),
            net_r_delta=float(variant.get("net_r", 0.0) - baseline.get("net_r", 0.0)),
            approval_rate_delta=float(variant.get("approval_rate", 0.0) - baseline.get("approval_rate", 0.0)),
            win_rate_delta=float(variant.get("win_rate", 0.0) - baseline.get("win_rate", 0.0)),
            profit_factor_delta=float(variant.get("profit_factor", 0.0) - baseline.get("profit_factor", 0.0)),
            avg_slippage_delta_bps=float(variant.get("avg_slippage_bps", 0.0) - baseline.get("avg_slippage_bps", 0.0)),
            drawdown_delta_r=float(variant.get("max_drawdown_r", 0.0) - baseline.get("max_drawdown_r", 0.0)),
            avg_entry_quality_delta=float(variant.get("avg_entry_quality", 0.0) - baseline.get("avg_entry_quality", 0.0)),
            avg_exit_quality_delta=float(variant.get("avg_exit_quality", 0.0) - baseline.get("avg_exit_quality", 0.0)),
            reason_codes=[],
        )
