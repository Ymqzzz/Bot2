from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.adaptive.adaptive_types import DecisionNarrative
from app.intelligence.adaptive.decision_summary_schema import DecisionSummarySchema
from app.intelligence.adaptive.reason_chain_builder import ReasonChainBuilder
from app.intelligence.adaptive.rejection_explanation_builder import RejectionExplanationBuilder
from app.intelligence.adaptive.trade_intent_report import TradeIntentReport


@dataclass
class DecisionNarrativeGenerator:
    chain_builder: ReasonChainBuilder = ReasonChainBuilder()
    rejection_builder: RejectionExplanationBuilder = RejectionExplanationBuilder()
    intent_builder: TradeIntentReport = TradeIntentReport()

    def generate(
        self,
        *,
        approved: bool,
        confidence: float,
        size_multiplier: float,
        supports: list[str],
        objections: list[str],
        penalties: dict[str, float],
        candidate_strategy: str,
        order_style: str,
        invalidations: list[str],
        veto_sources: list[str],
    ) -> DecisionNarrative:
        chain = self.chain_builder.build(supports=supports, objections=objections, penalties=penalties)
        if approved:
            summary_text = "Approved with adaptive controls"
        else:
            summary_text = self.rejection_builder.explain(blocked=bool(veto_sources), veto_sources=veto_sources, penalties=penalties)

        summary = DecisionSummarySchema(
            decision="approved" if approved else "rejected",
            confidence=confidence,
            size_multiplier=size_multiplier,
            key_reason_chain=chain,
        )
        intent = self.intent_builder.build(
            candidate_strategy=candidate_strategy,
            order_style=order_style,
            invalidations=invalidations,
        )

        return DecisionNarrative(
            summary=summary_text,
            support_factors=supports,
            opposition_factors=objections,
            penalty_breakdown=penalties,
            invalidation_triggers=invalidations,
            execution_rationale=f"order_style={order_style}",
            json_report={"summary": summary.__dict__, "intent": intent},
        )
