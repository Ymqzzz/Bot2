from __future__ import annotations

from app.intelligence.adaptive.adaptive_types import NegotiationObjection


class DecisionDisputeTrace:
    def build(self, objections: list[NegotiationObjection]) -> list[str]:
        return [f"{o.source_engine}::{o.objection_type}::{o.message}" for o in objections]
