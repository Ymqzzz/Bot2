from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.adaptive.adaptive_types import NegotiationOutcome
from app.intelligence.adaptive.conflict_protocol import ConflictProtocol
from app.intelligence.adaptive.decision_dispute_trace import DecisionDisputeTrace
from app.intelligence.adaptive.soft_objection_penalty import SoftObjectionPenalty
from app.intelligence.adaptive.veto_reason_resolver import VetoReasonResolver


@dataclass
class EngineNegotiationLayer:
    conflict_protocol: ConflictProtocol = ConflictProtocol()
    veto_resolver: VetoReasonResolver = VetoReasonResolver()
    soft_penalty: SoftObjectionPenalty = SoftObjectionPenalty()
    dispute_trace: DecisionDisputeTrace = DecisionDisputeTrace()

    def evaluate(self, *, context: dict) -> NegotiationOutcome:
        objections = self.conflict_protocol.detect(context=context)
        veto_sources = self.veto_resolver.resolve(objections)
        soft_pen = self.soft_penalty.compute(objections)
        blocked = bool(veto_sources)
        return NegotiationOutcome(
            blocked=blocked,
            total_penalty=soft_pen,
            veto_sources=veto_sources,
            objections=objections,
            dispute_trace=self.dispute_trace.build(objections),
        )
