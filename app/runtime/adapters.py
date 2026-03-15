from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.runtime.engine import RuntimeCycleInput, RuntimeSnapshot


class ControlPlaneLifecycleAdapter:
    def __init__(self, pipeline: Any):
        self.pipeline = pipeline

    def evaluate(self, cycle_input: RuntimeCycleInput, snapshot: RuntimeSnapshot, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        control_snapshot = self.pipeline.run_cycle(
            asof=snapshot.timestamp,
            instruments=cycle_input.instruments,
            market_intel_snapshots=cycle_input.market_data,
            bars=cycle_input.bars,
            candidate_pool=candidates,
            open_positions=cycle_input.open_positions,
            edge_context={
                "session": snapshot.session,
                "regime": snapshot.regime,
                "health_scores": snapshot.health_scores,
                **cycle_input.context,
            },
        )
        return {
            "approved_candidate_ids": list(control_snapshot.allocation_decision.approved_candidate_ids),
            "event": control_snapshot.event_decision.to_flat_dict(),
            "regimes": {k: v.to_flat_dict() for k, v in control_snapshot.regime_decisions.items()},
            "execution": {k: v.to_flat_dict() for k, v in control_snapshot.execution_decisions.items()},
            "allocation": control_snapshot.allocation_decision.to_flat_dict(),
            "tactics": {},
        }


class TradeIntelLifecycleAdapter:
    def __init__(self, pipeline: Any):
        self.pipeline = pipeline

    def generate_candidates(self, cycle_input: RuntimeCycleInput, snapshot: RuntimeSnapshot) -> list[dict[str, Any]]:
        candidates = list(cycle_input.context.get("candidate_pool", []))
        prepared: list[dict[str, Any]] = []
        for candidate in candidates:
            instrument = candidate.get("instrument", "")
            prep = self.pipeline.prepare_trade(
                candidate=candidate,
                market_intel_snapshot=cycle_input.market_data.get(instrument, {}),
                portfolio_context={
                    "open_positions": cycle_input.open_positions,
                    "equity": snapshot.equity,
                    "open_risk": snapshot.open_risk,
                },
                runtime_context={
                    "session": snapshot.session,
                    "regime": snapshot.regime,
                    "health_scores": snapshot.health_scores,
                    **cycle_input.context,
                },
            )
            prepared.append(
                {
                    **candidate,
                    "trade_id": prep["trade_id"],
                    "block_trade": prep["block_trade"],
                    "trade_intel_reason_codes": prep["reason_codes"],
                }
            )
        return [candidate for candidate in prepared if not candidate.get("block_trade")]


class ResearchCoreLifecycleAdapter:
    def __init__(self, pipeline: Any | None):
        self.pipeline = pipeline

    def review(
        self,
        cycle_input: RuntimeCycleInput,
        snapshot: RuntimeSnapshot,
        candidates: list[dict[str, Any]],
        control_plane_state: dict[str, Any],
    ) -> dict[str, Any]:
        if self.pipeline is None:
            return {"enabled": False, "rejected_candidate_ids": [], "reason_codes": ["RESEARCH_CORE_DISABLED"]}

        rejected: list[str] = []
        decisions: dict[str, Any] = {}
        for candidate in candidates:
            decision = self.pipeline.meta_approve_candidate(
                candidate,
                {
                    "runtime_snapshot": asdict(snapshot),
                    "control_plane": control_plane_state,
                    **cycle_input.context,
                },
            )
            decisions[candidate["candidate_id"]] = decision.to_flat_dict()
            if decision.action != "approve":
                rejected.append(candidate["candidate_id"])

        return {
            "enabled": True,
            "rejected_candidate_ids": rejected,
            "decisions": decisions,
        }
