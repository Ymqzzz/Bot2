from __future__ import annotations

from research_core.models import ReplayResult, SimulationRun, CalibrationSnapshot, MetaApprovalDecision


def build_replay_report(replay_result: ReplayResult) -> str:
    return (
        f"Replay {replay_result.replay_id}: steps={replay_result.num_steps}, "
        f"approved={replay_result.num_approved}/{replay_result.num_candidates}, net_r={replay_result.net_r:.2f}, "
        f"divergences={len(replay_result.divergence_flags)}"
    )


def build_simulation_report(simulation_run: SimulationRun) -> str:
    return f"Simulation {simulation_run.simulation_id}: variants={len(simulation_run.variant_scenarios)}"


def build_calibration_report(calibration_snapshots: list[CalibrationSnapshot]) -> str:
    lines = ["Calibration report"]
    for snap in calibration_snapshots:
        lines.append(f"{snap.scope_type}:{snap.scope_key} n={snap.sample_size} rel={snap.reliability_score:.3f}")
    return "\n".join(lines)


def build_meta_audit_report(meta_decisions: list[MetaApprovalDecision]) -> str:
    return "\n".join(f"{d.candidate_id} -> {d.action} ({','.join(d.reason_codes)})" for d in meta_decisions)
