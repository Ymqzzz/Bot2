from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from .config import ControlPlaneConfig
from .correlation import CorrelationEngine
from .event_engine import EventEngine
from .execution_intel import ExecutionIntelligenceEngine
from .models import AllocationCandidate, AllocationDecision, ControlPlaneSnapshot, EventDecision, ExecutionDecision, OrderTacticPlan, PortfolioStateSnapshot, RegimeDecision

from .config import ControlPlaneConfig
from .event_engine import EventEngine
from .execution_intel import ExecutionIntelligenceEngine
from .models import ControlPlaneSnapshot
from .order_tactics import OrderTacticPlanner
from .portfolio_allocator import PortfolioAllocator
from .regime_engine import RegimeEngine
from .storage import ControlPlaneStorage


class ControlPlanePipeline:
    def __init__(self, config: ControlPlaneConfig, storage: ControlPlaneStorage | None = None):
        self.config = config
        self.correlation_engine = CorrelationEngine()
        self.regime_engine = RegimeEngine(config)
        self.event_engine = EventEngine(config)
        self.execution_engine = ExecutionIntelligenceEngine(config)
        self.allocator = PortfolioAllocator(config, self.correlation_engine)
        self.tactic_planner = OrderTacticPlanner(config)
        self.storage = storage or ControlPlaneStorage()

    def build_regime_decisions(self, instrument_snapshots: dict[str, dict], bars: dict[str, pd.DataFrame], event_decision: EventDecision) -> dict[str, RegimeDecision]:
        return {
            ins: self.regime_engine.classify_instrument_regime(ins, instrument_snapshots.get(ins), bars.get(ins), event_decision)
            for ins in sorted(instrument_snapshots.keys())
        }

    def build_event_decision(self, asof: datetime, instruments: list[str], market_intel_snapshots: dict[str, dict]) -> EventDecision:
        return self.event_engine.build_event_decision(asof, instruments, market_intel_snapshots)

    def build_execution_decisions(self, candidate_pool: list[dict], market_intel_snapshots: dict[str, dict], regime_decisions: dict[str, RegimeDecision], event_decision: EventDecision) -> dict[str, ExecutionDecision]:
        out: dict[str, ExecutionDecision] = {}
        for c in candidate_pool:
            cid = c["candidate_id"]
            ins = c["instrument"]
            out[cid] = self.execution_engine.evaluate_entry(c, market_intel_snapshots.get(ins, {}), regime_decisions[ins], event_decision, {})
        return out

    def allocate_candidates(self, candidate_pool: list[AllocationCandidate], portfolio_state: PortfolioStateSnapshot, regime_decisions: dict[str, RegimeDecision], event_decision: EventDecision, execution_decisions: dict[str, ExecutionDecision], edge_context: dict | None) -> AllocationDecision:
        return self.allocator.allocate(candidate_pool, portfolio_state)

    def build_tactic_plans(self, approved_candidates: list[dict], execution_decisions: dict[str, ExecutionDecision], regime_decisions: dict[str, RegimeDecision], event_decision: EventDecision) -> dict[str, OrderTacticPlan]:
        return {
            c["candidate_id"]: self.tactic_planner.build_tactic_plan(c, execution_decisions[c["candidate_id"]], regime_decisions[c["instrument"]], event_decision)
            for c in approved_candidates
        }

    def run_cycle(
        self,
        asof: datetime,
        instruments: list[str],
        market_intel_snapshots: dict[str, dict],
        bars: dict[str, pd.DataFrame],
        candidate_pool: list[dict],
        open_positions: list[dict],
        edge_context: dict | None = None,
    ) -> ControlPlaneSnapshot:
        asof = asof if asof.tzinfo else asof.replace(tzinfo=timezone.utc)
        event_decision = self.build_event_decision(asof, instruments, market_intel_snapshots)
        regime_decisions = self.build_regime_decisions(market_intel_snapshots, bars, event_decision)

        filtered_candidates = []
        alloc_candidates: list[AllocationCandidate] = []
        for c in candidate_pool:
            r = regime_decisions[c["instrument"]]
            strategy = c["strategy_name"]
            if strategy in r.blocked_strategies:
                continue
            if strategy in {"Breakout-Squeeze", "Squeeze-Breakout"} and not event_decision.allow_breakout:
                continue
            if strategy == "Range-MeanReversion" and not event_decision.allow_mean_reversion:
                continue
            filtered_candidates.append(c)

        execution_decisions = self.build_execution_decisions(filtered_candidates, market_intel_snapshots, regime_decisions, event_decision)
        executable = [c for c in filtered_candidates if execution_decisions[c["candidate_id"]].allow_entry]

        portfolio_state = self.allocator.build_portfolio_state(open_positions, [], {})
        for c in executable:
            rd = regime_decisions[c["instrument"]]
            ed = execution_decisions[c["candidate_id"]]
            ac = AllocationCandidate(
                candidate_id=c["candidate_id"], instrument=c["instrument"], strategy_name=c["strategy_name"], side=c["side"], setup_type=c.get("setup_type", "default"),
                expected_value=float(c.get("expected_value", 0.0)), confidence=float(c.get("confidence", 0.0)), risk_fraction_requested=float(c.get("risk_fraction_requested", 0.0)),
                risk_fraction_capped=None, regime_score=rd.regime_confidence, event_score=event_decision.event_risk_multiplier, execution_score=ed.fill_probability_score,
                edge_score=float(c.get("edge_score", 0.5)), portfolio_fit_score=1.0, macro_cluster_key=self.correlation_engine.cluster_macro_expression(c),
                currency_exposure_map=self.correlation_engine.compute_currency_exposure(c), correlation_bucket=None,
                priority_score=0.0, blocked=False, block_reason_codes=[]
            )
            ac.priority_score = self.allocator.score_candidate_priority(ac, rd, event_decision, ed, edge_context)
            alloc_candidates.append(ac)

        allocation = self.allocate_candidates(alloc_candidates, portfolio_state, regime_decisions, event_decision, execution_decisions, edge_context)
        approved = [c for c in executable if c["candidate_id"] in allocation.approved_candidate_ids]
        tactics = self.build_tactic_plans(approved, execution_decisions, regime_decisions, event_decision)

        for rd in regime_decisions.values():
            self.storage.persist("regime", rd.to_flat_dict(), instrument=rd.instrument)
        self.storage.persist("event", event_decision.to_flat_dict())
        for cid, ed in execution_decisions.items():
            self.storage.persist("execution", ed.to_flat_dict(), candidate_id=cid, instrument=ed.instrument)
        self.storage.persist("allocation", allocation.to_flat_dict())
        self.storage.persist("portfolio", portfolio_state.to_flat_dict())
        for cid, tp in tactics.items():
            self.storage.persist("tactic", tp.to_flat_dict(), candidate_id=cid, instrument=tp.instrument)

        return ControlPlaneSnapshot(
            asof=asof,
            regime_decisions=regime_decisions,
            event_decision=event_decision,
            execution_decisions=execution_decisions,
            allocation_decision=allocation,
            portfolio_state=portfolio_state,
            reason_codes=[],
        )
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
