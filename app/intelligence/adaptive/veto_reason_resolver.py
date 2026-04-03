from __future__ import annotations

from app.intelligence.adaptive.adaptive_types import NegotiationObjection


class VetoReasonResolver:
    def resolve(self, objections: list[NegotiationObjection]) -> list[str]:
        return [f"{o.source_engine}:{o.objection_type}" for o in objections if o.hard_veto]
