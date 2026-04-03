from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .attribution import TradeAttributionEngine
from .decision_engine import DecisionEngine, build_decision_engine
from .execution_simulator import ExecutionSimulator
from .config import TradeIntelConfig
from .edge_decay import EdgeDecayEngine
from .events import TradeIntelEventEmitter
from .exits import SmartExitEngine
from .health_monitor import HealthMonitor
from .lifecycle import TradeLifecycleManager
from .trade_attribution_engine import LiveAttributionEngine
from .models import TradeLifecycleRecord
from .performance_store import PerformanceStore
from .regime_transition_model import RegimeTransitionModel
from .signal_graph import SignalDependencyGraph
from .sizing import AdaptiveSizingEngine
from .storage import TradeIntelStorage


class TradeIntelPipeline:
    def __init__(
        self,
        config: TradeIntelConfig,
        sizing_engine: AdaptiveSizingEngine,
        exit_engine: SmartExitEngine,
        attribution_engine: TradeAttributionEngine,
        performance_store: PerformanceStore,
        edge_engine: EdgeDecayEngine,
        decision_engine: DecisionEngine,
        execution_simulator: ExecutionSimulator,
        regime_model: RegimeTransitionModel,
        signal_graph: SignalDependencyGraph,
        health_monitor: HealthMonitor,
        live_attribution: LiveAttributionEngine,
        lifecycle_manager: TradeLifecycleManager,
        storage: TradeIntelStorage,
        events: TradeIntelEventEmitter,
    ):
        self.config = config
        self.sizing_engine = sizing_engine
        self.exit_engine = exit_engine
        self.attribution_engine = attribution_engine
        self.performance_store = performance_store
        self.edge_engine = edge_engine
        self.decision_engine = decision_engine
        self.execution_simulator = execution_simulator
        self.regime_model = regime_model
        self.signal_graph = signal_graph
        self.health_monitor = health_monitor
        self.live_attribution = live_attribution
        self.lifecycle_manager = lifecycle_manager
        self.storage = storage
        self.events = events

    def prepare_trade(self, candidate: dict[str, Any], market_intel_snapshot: dict[str, Any], portfolio_context: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        edge_snaps = self.performance_store.get_relevant_edge_snapshots(candidate)
        block_edge, block_reasons = self.edge_engine.should_block_trade(edge_snaps)
        if block_edge:
            self.events.trade_blocked_by_edge_health({"candidate": candidate, "reason_codes": block_reasons})
        health_state = self.health_monitor.assess(market_intel_snapshot, runtime_context)
        if health_state.degraded:
            self.events.health_degraded({"status": health_state.status, "reason_codes": health_state.reason_codes})
        regime_state = self.regime_model.update(runtime_context)
        signal_report = self.signal_graph.analyze(candidate, runtime_context)
        execution_est = self.execution_simulator.estimate(candidate, market_intel_snapshot)
        distribution = self.decision_engine.build_distribution(candidate, execution_est, signal_report, regime_state, market_intel_snapshot)
        decision = self.decision_engine.decide(
            candidate,
            distribution,
            execution_est,
            signal_report,
            regime_state,
            health_state.block_trading,
            health_state.risk_multiplier_cap,
            health_state.reason_codes,
            str(runtime_context.get("session_name", "UNKNOWN")),
        )
        sizing = self.sizing_engine.recommend_size(
            candidate,
            market_intel_snapshot,
            portfolio_context,
            edge_snaps,
            runtime_context.get("recent_performance", {}),
        )
        if decision.size_multiplier_cap < 1.0 and not sizing.block_trade:
            sizing.recommended_risk_fraction *= decision.size_multiplier_cap
            sizing.size_multiplier_total *= decision.size_multiplier_cap
            sizing.reason_codes.extend(decision.reason_codes)
        blocked = block_edge or sizing.block_trade or (not decision.approved)
        if not decision.approved:
            self.events.decision_declined({"candidate": candidate, "reason_codes": decision.decline_reason_hierarchy})
        elif decision.approval_status == "degraded_approved":
            self.events.decision_degraded_approved({"candidate": candidate, "reason_codes": decision.reason_codes})
        fp = self.attribution_engine.build_trade_fingerprint(candidate, runtime_context, sizing.reason_codes, block_reasons)
        plan = self.exit_engine.build_initial_exit_plan({
            "trade_id": fp.trade_id,
            "setup_type": fp.setup_type,
            "entry_price": candidate.get("entry_price", 0.0),
            "stop_loss": candidate.get("stop_loss", 0.0),
            "side": candidate.get("side", "BUY"),
        })
        rec = TradeLifecycleRecord(
            fingerprint=fp,
            entry_quality=None,
            path_metrics=None,
            exit_quality=None,
            attribution=None,
            sizing=sizing,
            exit_plan=plan,
            status="planned",
            opened_ts=None,
            closed_ts=None,
            realized_pnl=None,
            realized_r=None,
        )
        self.lifecycle_manager.register_planned_trade(rec)
        self.storage.append_jsonl("trade_fingerprints", fp.to_flat_dict())
        self.storage.append_jsonl("trade_sizing_decisions", sizing.to_flat_dict())
        self.storage.append_jsonl("trade_exit_plans", plan.to_flat_dict())
        self.storage.append_jsonl("trade_decision_distributions", distribution.to_dict())
        self.storage.append_jsonl("trade_decisions", decision.to_dict())
        return {
            "trade_id": fp.trade_id,
            "fingerprint": fp,
            "sizing_decision": sizing,
            "exit_plan": plan,
            "block_trade": blocked,
            "reason_codes": sizing.reason_codes + block_reasons + decision.reason_codes,
            "decision": decision,
            "distribution": distribution,
            "execution_estimate": execution_est,
            "regime_transition_state": regime_state,
        }

    def on_trade_open(self, trade_info: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
        trade_id = str(trade_info["trade_id"])
        rec = self.lifecycle_manager.register_open_trade(trade_id, float(trade_info.get("entry_filled", 0.0)))
        return {"trade_id": trade_id, "status": rec.status if rec else "missing"}

    def on_trade_update(self, trade_info: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
        trade_id = str(trade_info["trade_id"])
        rec = self.lifecycle_manager.get_open_trade_record(trade_id)
        if not rec:
            return {"trade_id": trade_id, "status": "missing"}
        live_state = {
            "r_multiple": float(trade_info.get("r_multiple", 0.0)),
            "seconds_held": int(trade_info.get("seconds_held", 0)),
            "structure_confirmed": bool(trade_info.get("structure_confirmed", True)),
        }
        instruction = self.exit_engine.evaluate_live_exit({"max_hold_seconds": rec.exit_plan.max_hold_seconds if rec.exit_plan else None}, live_state, market_context)
        return {"trade_id": trade_id, "status": rec.status, "instruction": instruction}

    def on_trade_partial(self, trade_info: dict[str, Any], partial_info: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
        trade_id = str(trade_info["trade_id"])
        self.lifecycle_manager.register_partial_exit(trade_id)
        self.events.partial_taken({"trade_id": trade_id, **partial_info})
        return {"trade_id": trade_id, "status": "partially_closed"}

    def on_trade_close(self, trade_info: dict[str, Any], close_info: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
        trade_id = str(trade_info["trade_id"])
        rec = self.lifecycle_manager.get_open_trade_record(trade_id)
        if not rec:
            return {"trade_id": trade_id, "status": "missing"}
        planned_entry = rec.fingerprint.entry_planned
        filled_entry = float(rec.fingerprint.entry_filled or planned_entry)
        entry_q = self.attribution_engine.assess_entry_quality(planned_entry, filled_entry, rec.fingerprint.side, market_context)
        risk = abs(rec.fingerprint.entry_planned - rec.fingerprint.stop_initial)
        pnl_path = list(close_info.get("pnl_path", [float(close_info.get("realized_pnl", 0.0))]))
        path = self.attribution_engine.compute_path_metrics(trade_id, risk, int(close_info.get("bars_held", 0)), int(close_info.get("seconds_held", 0)), pnl_path, close_info.get("spread_scores", []), close_info.get("vol_scores", []))
        realized_r = float(close_info.get("realized_r", 0.0))
        exit_q = self.attribution_engine.assess_exit_quality(path, {**close_info, "realized_r": realized_r})
        attr = self.attribution_engine.attribute_outcome(trade_id, rec.fingerprint, entry_q, exit_q, path, realized_r, market_context)
        final = self.attribution_engine.finalize_lifecycle_record(rec, entry_q, path, exit_q, attr, float(close_info.get("realized_pnl", 0.0)), realized_r)
        online_attr = self.live_attribution.process_closed_trade(
            {
                "ev_r": rec.fingerprint.expected_value_raw,
                "instrument": rec.fingerprint.instrument,
                "regime": rec.fingerprint.regime_name,
                "session": rec.fingerprint.session_name,
                "supporting_engines": market_context.get("supporting_engines", []),
                "opposing_engines": market_context.get("opposing_engines", []),
            },
            close_info,
        )
        self.lifecycle_manager.close_trade(trade_id)
        self.performance_store.update_with_closed_trade(final)
        self.storage.append_jsonl("trade_lifecycle_records", final.to_flat_dict())
        self.storage.append_jsonl("trade_online_attribution", {"trade_id": trade_id, "engine_trust": online_attr.engine_trust, "labels": online_attr.labels})
        self.events.trade_finalized({"trade_id": trade_id, "outcome": attr.outcome_label})
        return {"trade_id": trade_id, "status": "closed", "outcome": attr.outcome_label}

    def get_trade_block_decision(self, context: dict[str, Any]) -> tuple[bool, list[str]]:
        snaps = self.performance_store.get_relevant_edge_snapshots(context)
        return self.edge_engine.should_block_trade(snaps)

    def get_sizing_decision(self, context: dict[str, Any]) -> Any:
        return self.prepare_trade(context["candidate"], context.get("market", {}), context.get("portfolio", {}), context.get("runtime", {}))["sizing_decision"]

    def get_exit_instruction(self, trade_context: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
        return self.on_trade_update(trade_context, market_context)


def build_default_pipeline(config: TradeIntelConfig) -> TradeIntelPipeline:
    edge = EdgeDecayEngine(config)
    return TradeIntelPipeline(
        config=config,
        sizing_engine=AdaptiveSizingEngine(config),
        exit_engine=SmartExitEngine(config),
        attribution_engine=TradeAttributionEngine(config),
        performance_store=PerformanceStore(config, edge),
        edge_engine=edge,
        decision_engine=build_decision_engine(),
        execution_simulator=ExecutionSimulator(),
        regime_model=RegimeTransitionModel(),
        signal_graph=SignalDependencyGraph(),
        health_monitor=HealthMonitor(),
        live_attribution=LiveAttributionEngine(),
        lifecycle_manager=TradeLifecycleManager(),
        storage=TradeIntelStorage(config),
        events=TradeIntelEventEmitter(),
    )
