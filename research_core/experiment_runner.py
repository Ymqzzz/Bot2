from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from research_core.models import ScenarioDefinition, SimulationRun
from research_core.reason_codes import SIM_BASELINE, SIM_COMPLETE


class ExperimentRunner:
    def __init__(self, simulator):
        self.simulator = simulator

    def run_experiment_set(self, start_ts: datetime, end_ts: datetime, instruments: list[str], scenarios: list[ScenarioDefinition]) -> SimulationRun:
        baseline = self.simulator.run_baseline({"scenario_id": "baseline", "net_r": 0.0, "approval_rate": 0.0})
        results = {"baseline": baseline}
        comparisons: dict[str, dict] = {}
        for scenario in scenarios:
            variant = self.simulator.run_variant(baseline, scenario)
            results[scenario.scenario_id] = variant
            comparisons[scenario.scenario_id] = self.simulator.compare_runs(baseline, variant).to_flat_dict()
        return SimulationRun(
            simulation_id=f"sim-{uuid4().hex[:10]}",
            baseline_scenario=ScenarioDefinition("baseline", "baseline", "baseline", {}, {}, {}),
            variant_scenarios=scenarios,
            start_ts=start_ts,
            end_ts=end_ts,
            results_by_scenario=results,
            comparisons=comparisons,
            reason_codes=[SIM_BASELINE, SIM_COMPLETE],
        )

    def rank_variants(self, simulation_run: SimulationRun) -> list[dict]:
        ranked = []
        for scenario_id, comparison in simulation_run.comparisons.items():
            ranked.append({"scenario_id": scenario_id, "net_r_delta": float(comparison.get("net_r_delta", 0.0))})
        ranked.sort(key=lambda row: row["net_r_delta"], reverse=True)
        return ranked

    def export_experiment_summary(self, simulation_run: SimulationRun) -> str:
        rows = [f"simulation_id={simulation_run.simulation_id}"]
        for row in self.rank_variants(simulation_run):
            rows.append(f"{row['scenario_id']}: net_r_delta={row['net_r_delta']:.4f}")
        return "\n".join(rows)
