from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import NegotiationObjection


class SoftObjectionPenalty:
    def compute(self, objections: list[NegotiationObjection]) -> float:
        soft = [o for o in objections if not o.hard_veto]
        if not soft:
            return 0.0
        weighted = sum(o.severity * (1.25 if o.objection_type == "fill_quality" else 1.0) for o in soft)
        return clamp(weighted / max(len(soft), 1))
