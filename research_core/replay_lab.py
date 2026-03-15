from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from research_core.models import ReplayResult, ReplayStepRecord
from research_core.reason_codes import REPLAY_COMPLETE, REPLAY_DETERMINISTIC_OK, REPLAY_DIVERGENCE_DETECTED
from research_core.replay_data import ReplayStream


class ReplayLab:
    def __init__(self, stream_loader):
        self.stream_loader = stream_loader

    def replay_step(self, step_ts: datetime, state_context: dict) -> ReplayStepRecord:
        candidates = list(state_context.get("candidates", []))
        approved = list(state_context.get("approved", []))
        blocked = [c for c in candidates if c not in approved]
        return ReplayStepRecord(
            step_ts=step_ts,
            instrument=str(state_context.get("instrument", "")),
            market_intel_ref=state_context.get("market_intel_ref"),
            trade_intel_ref=state_context.get("trade_intel_ref"),
            control_plane_ref=state_context.get("control_plane_ref"),
            candidate_ids=candidates,
            approved_candidate_ids=approved,
            blocked_candidate_ids=blocked,
            meta_decision_ids=list(state_context.get("meta_decision_ids", [])),
            execution_outcomes=list(state_context.get("execution_outcomes", [])),
            open_positions_snapshot=dict(state_context.get("open_positions", {})),
            portfolio_state_snapshot=dict(state_context.get("portfolio", {})),
            warnings=list(state_context.get("warnings", [])),
        )

    def run_replay(self, start_ts: datetime, end_ts: datetime, instruments: list[str], scenario=None) -> ReplayResult:
        replay_stream: ReplayStream = self.stream_loader(start_ts, end_ts, instruments, scenario)
        step_records: list[ReplayStepRecord] = []
        num_candidates = num_approved = num_executed = 0
        pnl_r = 0.0
        for ts in replay_stream.steps:
            for instrument in instruments:
                ctx = dict(replay_stream.aligned.get(ts, {}))
                ctx["instrument"] = instrument
                step = self.replay_step(ts, ctx)
                step_records.append(step)
                num_candidates += len(step.candidate_ids)
                num_approved += len(step.approved_candidate_ids)
                num_executed += len(step.execution_outcomes)
                pnl_r += sum(float(o.get("r", 0.0)) for o in step.execution_outcomes)
        num_rejected = max(0, num_candidates - num_approved)
        approval_rate = num_approved / num_candidates if num_candidates else 0.0
        reason_codes = [REPLAY_COMPLETE, REPLAY_DETERMINISTIC_OK]
        divergence_flags = list(replay_stream.divergences)
        if divergence_flags:
            reason_codes.append(REPLAY_DIVERGENCE_DETECTED)
        return ReplayResult(
            replay_id=f"replay-{uuid4().hex[:10]}",
            start_ts=start_ts,
            end_ts=end_ts,
            instruments=instruments,
            num_steps=len(step_records),
            num_candidates=num_candidates,
            num_approved=num_approved,
            num_rejected=num_rejected,
            num_executed=num_executed,
            num_closed_trades=num_executed,
            gross_pnl=pnl_r,
            net_pnl=pnl_r,
            net_r=pnl_r,
            max_drawdown_r=min(0.0, pnl_r),
            approval_rate=approval_rate,
            step_records=step_records,
            divergence_flags=divergence_flags,
            reason_codes=reason_codes,
        )

    def compare_replay_to_recorded_live(self, replay_result: ReplayResult, recorded_result: dict) -> dict:
        out = {"candidate_divergence": 0, "approval_divergence": 0, "execution_divergence": 0, "exit_divergence": 0}
        out["candidate_divergence"] = replay_result.num_candidates - int(recorded_result.get("num_candidates", 0))
        out["approval_divergence"] = replay_result.num_approved - int(recorded_result.get("num_approved", 0))
        out["execution_divergence"] = replay_result.num_executed - int(recorded_result.get("num_executed", 0))
        out["exit_divergence"] = replay_result.num_closed_trades - int(recorded_result.get("num_closed_trades", 0))
        return out
