from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class EngineInput:
    timestamp: datetime
    instrument: str
    trace_id: str
    features: dict[str, float]
    bars: list[dict]
    context: dict


class IntelligenceEngine(Protocol):
    def compute(self, data: EngineInput):
        ...
