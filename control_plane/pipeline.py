from __future__ import annotations

from datetime import datetime, timezone

from .config import ControlPlaneConfig
from .event_engine import EventEngine
from .execution_intel import ExecutionIntelligenceEngine
from .models import ControlPlaneSnapshot
from .order_tactics import OrderTacticPlanner
from .portfolio_allocator import PortfolioAllocator
from .regime_engine import RegimeEngine
from .storage import ControlPlaneStorage


class ControlPlanePipeline:
    def __init__(self, config: ControlPlaneConfig | None = None, calendar_provider=None) -> None:
        self.config = config or ControlPlaneConfig()
        self.regime_engine = RegimeEngine(self.config)
        self.event_engine = EventEngine(self.config, calendar_provider=calendar_provider)
        self.execution_engine = ExecutionIntelligenceEngine(self.config)
        self.portfolio_allocator = PortfolioAllocator(self.config)
        self.order_tactics = OrderTacticPlanner(self.config)
        self.storage = ControlPlaneStorage()

    def build_regime_decisions(self, instrument_snapshots, bars, event_decision):
        out = {}
        for instrument, snap in instrument_snapshots.items():
            out[instrument] = self.regime_engine.classify_instrument_regime(instrument, snap, bars.get(instrument), event_decision)
        return out

    def build_event_decision(self, asof, instruments, market_intel_snapshots):
        return self.event_engine.build_event_decision(asof, instruments, market_intel_snapshots)

    def build_execution_decisions(self, candidate_pool, market_intel_snapshots, regime_decisions, event_decision):
        out = {}
        for c in candidate_pool:
            out[c.candidate_id] = self.execution_engine.evaluate_entry(c, market_intel_snapshots.get(c.instrument, {}), regime_decisions[c.instrument], event_decision, {})
        return out

    def allocate_candidates(self, candidate_pool, portfolio_state, regime_decisions, event_decision, execution_decisions, edge_context):
        for c in candidate_pool:
            c.priority_score = self.portfolio_allocator.score_candidate_priority(c, regime_decisions[c.instrument], event_decision, execution_decisions[c.candidate_id], edge_context)
        return self.portfolio_allocator.allocate(candidate_pool, portfolio_state)

    def build_tactic_plans(self, approved_candidates, execution_decisions, regime_decisions, event_decision):
        return {
            c.candidate_id: self.order_tactics.build_tactic_plan(c, execution_decisions[c.candidate_id], regime_decisions[c.instrument], event_decision)
            for c in approved_candidates
        }

    def run_cycle(self, asof: datetime | None = None, instrument_snapshots=None, bars=None, candidate_pool=None, open_positions=None, edge_context=None):
        asof = asof or datetime.now(timezone.utc)
        instrument_snapshots = instrument_snapshots or {}
        bars = bars or {}
        candidate_pool = candidate_pool or []
        open_positions = open_positions or []
        event_decision = self.build_event_decision(asof, list(instrument_snapshots.keys()), instrument_snapshots)
        regime_decisions = self.build_regime_decisions(instrument_snapshots, bars, event_decision)
        execution_decisions = self.build_execution_decisions(candidate_pool, instrument_snapshots, regime_decisions, event_decision)
        portfolio_state = self.portfolio_allocator.build_portfolio_state(open_positions, candidate_pool, {})
        allocation_decision = self.allocate_candidates(candidate_pool, portfolio_state, regime_decisions, event_decision, execution_decisions, edge_context or {})
        approved = [c for c in candidate_pool if c.candidate_id in allocation_decision.approved_candidate_ids]
        tactic_plans = self.build_tactic_plans(approved, execution_decisions, regime_decisions, event_decision)
        snap = ControlPlaneSnapshot(asof=asof, regime_decisions=regime_decisions, event_decision=event_decision, execution_decisions=execution_decisions, allocation_decision=allocation_decision, portfolio_state=portfolio_state, reason_codes=[])
        self.storage.append_jsonl("regime_decisions", {k: v.to_flat_dict() for k, v in regime_decisions.items()})
        self.storage.append_jsonl("event_decisions", event_decision.to_flat_dict())
        self.storage.append_jsonl("execution_decisions", {k: v.to_flat_dict() for k, v in execution_decisions.items()})
        self.storage.append_jsonl("allocation_decisions", allocation_decision.to_flat_dict())
        self.storage.append_jsonl("portfolio_state_snapshots", portfolio_state.to_flat_dict())
        self.storage.append_jsonl("order_tactic_plans", {k: v.to_flat_dict() for k, v in tactic_plans.items()})
        return snap
