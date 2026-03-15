from __future__ import annotations

from dataclasses import asdict

from app.execution.routing import choose_order_type
from app.execution.scheduling import build_clip_plan
from app.models.schema import SignalCandidate
from app.monitoring.audit import AuditSink
from app.monitoring.events import EventBus
from app.risk.portfolio_adapter import PortfolioContext, apply_caps


class DecisionGraph:
    def __init__(self, event_bus: EventBus, audit_sink: AuditSink):
        self.event_bus = event_bus
        self.audit_sink = audit_sink

    def evaluate(
        self,
        trace_id: str,
        candidate: SignalCandidate,
        spread_pctile: float,
        liquidity_factor: float,
        has_near_event: bool,
        signed_units: int,
        sizing_diagnostics: dict,
        portfolio_ctx: PortfolioContext,
        min_score: float,
        max_spread_pctile: float,
        daily_risk_pct: float,
        cluster_risk_pct: float,
    ) -> dict:
        self.event_bus.emit("signal_emitted", trace_id, {"strategy": candidate.strategy, "instrument": candidate.instrument, "score": candidate.score})

        if candidate.score < min_score:
            out = {"approved": False, "reason": "score_below_threshold"}
            self.event_bus.emit("signal_rejected", trace_id, out)
            return out

        if spread_pctile > max_spread_pctile:
            out = {"approved": False, "reason": "spread_gate"}
            self.event_bus.emit("signal_rejected", trace_id, out)
            return out

        proposal = {
            "instrument": candidate.instrument,
            "entry_price": candidate.entry_price,
            "stop_loss": candidate.stop_loss,
            "take_profit": candidate.take_profit,
            "signed_units": int(signed_units),
            "expected_value_proxy": candidate.score,
            "strategy": candidate.strategy,
            "sizing_rationale": dict(sizing_diagnostics),
        }
        capped = apply_caps(proposal, portfolio_ctx, daily_risk_pct=daily_risk_pct, cluster_risk_pct=cluster_risk_pct)
        if capped.get("blocked"):
            out = {"approved": False, "reason": capped.get("block_reason", "risk_block")}
            self.event_bus.emit("risk_blocked", trace_id, out)
            return out

        order_type = choose_order_type(candidate.strategy, breakout_mag=candidate.score, liquidity_factor=liquidity_factor, spread_pctile=spread_pctile)
        clips = build_clip_plan(units=int(signed_units), liquidity_factor=liquidity_factor, has_near_event=has_near_event)
        result = {
            "approved": True,
            "proposal": capped,
            "sizing": dict(sizing_diagnostics),
            "order_type": order_type,
            "clips": clips,
            "candidate": asdict(candidate),
        }
        self.event_bus.emit("order_submitted", trace_id, {"instrument": candidate.instrument, "order_type": order_type, "clips": clips})
        self.audit_sink.append({
            "trace_id": trace_id,
            "decision_hash": self.audit_sink.snapshot_hash(result),
            "decision": result,
            "sizing_rationale": dict(sizing_diagnostics),
        })
        return result
