from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .config import ControlPlaneConfig
from .correlation import CorrelationEngine
from .event_engine import EventEngine
from .execution_intel import ExecutionIntelligenceEngine
from .models import (
    AllocationCandidate,
    AllocationDecision,
    ControlPlaneSnapshot,
    EventDecision,
    ExecutionDecision,
    OrderTacticPlan,
    PortfolioStateSnapshot,
    RegimeDecision,
)
from .order_tactics import OrderTacticPlanner
from .portfolio_allocator import PortfolioAllocator
from .regime_engine import RegimeEngine
from .storage import ControlPlaneStorage


class ControlPlanePipeline:
    def __init__(
        self,
        config: ControlPlaneConfig | None = None,
        storage: ControlPlaneStorage | None = None,
        calendar_provider=None,
    ) -> None:
        self.config = config or ControlPlaneConfig()
        self.correlation_engine = CorrelationEngine()
        self.regime_engine = RegimeEngine(self.config)
        self.event_engine = EventEngine(self.config, calendar_provider=calendar_provider)
        self.execution_engine = ExecutionIntelligenceEngine(self.config)
        self.allocator = PortfolioAllocator(self.config, self.correlation_engine)
        self.tactic_planner = OrderTacticPlanner(self.config)
        self.storage = storage or ControlPlaneStorage()

    @staticmethod
    def _as_dict_candidate(candidate: AllocationCandidate | dict[str, Any]) -> dict[str, Any]:
        if isinstance(candidate, AllocationCandidate):
            return {
                "candidate_id": candidate.candidate_id,
                "instrument": candidate.instrument,
                "strategy_name": candidate.strategy_name,
                "side": candidate.side,
                "setup_type": candidate.setup_type,
                "expected_value": candidate.expected_value,
                "confidence": candidate.confidence,
                "risk_fraction_requested": candidate.risk_fraction_requested,
                "edge_score": candidate.edge_score,
            }
        return candidate

    def build_regime_decisions(
        self,
        instrument_snapshots: dict[str, dict],
        bars: dict[str, pd.DataFrame],
        event_decision: EventDecision,
    ) -> dict[str, RegimeDecision]:
        return {
            ins: self.regime_engine.classify_instrument_regime(ins, instrument_snapshots.get(ins), bars.get(ins), event_decision)
            for ins in sorted(instrument_snapshots.keys())
        }

    def build_event_decision(self, asof: datetime, instruments: list[str], market_intel_snapshots: dict[str, dict]) -> EventDecision:
        return self.event_engine.build_event_decision(asof, instruments, market_intel_snapshots)

    def build_execution_decisions(
        self,
        candidate_pool: list[AllocationCandidate | dict[str, Any]],
        market_intel_snapshots: dict[str, dict],
        regime_decisions: dict[str, RegimeDecision],
        event_decision: EventDecision,
    ) -> dict[str, ExecutionDecision]:
        out: dict[str, ExecutionDecision] = {}
        for candidate in candidate_pool:
            c = self._as_dict_candidate(candidate)
            cid = c["candidate_id"]
            ins = c["instrument"]
            out[cid] = self.execution_engine.evaluate_entry(c, market_intel_snapshots.get(ins, {}), regime_decisions[ins], event_decision, {})
        return out

    def allocate_candidates(
        self,
        candidate_pool: list[AllocationCandidate],
        portfolio_state: PortfolioStateSnapshot,
        regime_decisions: dict[str, RegimeDecision],
        event_decision: EventDecision,
        execution_decisions: dict[str, ExecutionDecision],
        edge_context: dict | None,
    ) -> AllocationDecision:
        return self.allocator.allocate(candidate_pool, portfolio_state)

    def build_tactic_plans(
        self,
        approved_candidates: list[AllocationCandidate | dict[str, Any]],
        execution_decisions: dict[str, ExecutionDecision],
        regime_decisions: dict[str, RegimeDecision],
        event_decision: EventDecision,
    ) -> dict[str, OrderTacticPlan]:
        out: dict[str, OrderTacticPlan] = {}
        for candidate in approved_candidates:
            c = self._as_dict_candidate(candidate)
            cid = c["candidate_id"]
            out[cid] = self.tactic_planner.build_tactic_plan(c, execution_decisions[cid], regime_decisions[c["instrument"]], event_decision)
        return out

    def run_cycle(
        self,
        asof: datetime | None = None,
        instruments: list[str] | None = None,
        market_intel_snapshots: dict[str, dict] | None = None,
        bars: dict[str, pd.DataFrame] | None = None,
        candidate_pool: list[AllocationCandidate | dict[str, Any]] | None = None,
        open_positions: list[dict] | None = None,
        edge_context: dict | None = None,
        instrument_snapshots: dict[str, dict] | None = None,
    ) -> ControlPlaneSnapshot:
        asof = asof if asof is not None else datetime.now(timezone.utc)
        asof = asof if asof.tzinfo else asof.replace(tzinfo=timezone.utc)
        snapshots = market_intel_snapshots if market_intel_snapshots is not None else instrument_snapshots or {}
        bars = bars or {}
        candidate_pool = candidate_pool or []
        open_positions = open_positions or []
        instruments = instruments or sorted(snapshots.keys())

        event_decision = self.build_event_decision(asof, instruments, snapshots)
        regime_decisions = self.build_regime_decisions(snapshots, bars, event_decision)

        normalized_candidates = [self._as_dict_candidate(c) for c in candidate_pool]
        filtered_candidates: list[dict[str, Any]] = []
        alloc_candidates: list[AllocationCandidate] = []
        for c in normalized_candidates:
            regime = regime_decisions[c["instrument"]]
            strategy = c["strategy_name"]
            if strategy in regime.blocked_strategies:
                continue
            if strategy in {"Breakout-Squeeze", "Squeeze-Breakout"} and not event_decision.allow_breakout:
                continue
            if strategy == "Range-MeanReversion" and not event_decision.allow_mean_reversion:
                continue
            filtered_candidates.append(c)

        execution_decisions = self.build_execution_decisions(filtered_candidates, snapshots, regime_decisions, event_decision)
        executable = [c for c in filtered_candidates if execution_decisions[c["candidate_id"]].allow_entry]

        portfolio_state = self.allocator.build_portfolio_state(open_positions, [], {})
        for c in executable:
            rd = regime_decisions[c["instrument"]]
            ed = execution_decisions[c["candidate_id"]]
            ac = AllocationCandidate(
                candidate_id=c["candidate_id"],
                instrument=c["instrument"],
                strategy_name=c["strategy_name"],
                side=c["side"],
                setup_type=c.get("setup_type", "default"),
                expected_value=float(c.get("expected_value", 0.0)),
                confidence=float(c.get("confidence", 0.0)),
                risk_fraction_requested=float(c.get("risk_fraction_requested", 0.0)),
                risk_fraction_capped=None,
                regime_score=rd.regime_confidence,
                event_score=event_decision.event_risk_multiplier,
                execution_score=ed.fill_probability_score,
                edge_score=float(c.get("edge_score", 0.5)),
                portfolio_fit_score=1.0,
                macro_cluster_key=self.correlation_engine.cluster_macro_expression(c),
                currency_exposure_map=self.correlation_engine.compute_currency_exposure(c),
                correlation_bucket=None,
                priority_score=0.0,
                blocked=False,
                block_reason_codes=[],
            )
            ac.priority_score = self.allocator.score_candidate_priority(ac, rd, event_decision, ed, edge_context)
            alloc_candidates.append(ac)

        allocation = self.allocate_candidates(alloc_candidates, portfolio_state, regime_decisions, event_decision, execution_decisions, edge_context)
        approved = [c for c in executable if c["candidate_id"] in allocation.approved_candidate_ids]
        _ = self.build_tactic_plans(approved, execution_decisions, regime_decisions, event_decision)

        return ControlPlaneSnapshot(
            asof=asof,
            regime_decisions=regime_decisions,
            event_decision=event_decision,
            execution_decisions=execution_decisions,
            allocation_decision=allocation,
            portfolio_state=portfolio_state,
            reason_codes=[],
        )
