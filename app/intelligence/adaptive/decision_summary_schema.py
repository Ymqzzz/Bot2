from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecisionSummarySchema:
    decision: str
    confidence: float
    size_multiplier: float
    key_reason_chain: list[str] = field(default_factory=list)
