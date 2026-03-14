from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


@dataclass(frozen=True)
class MarketIntelEvent:
    asof: datetime
    instrument: str
    event_type: str
    payload: Dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._events: List[MarketIntelEvent] = []

    def emit(self, event: MarketIntelEvent) -> None:
        self._events.append(event)

    def recent(self, limit: int = 100) -> List[MarketIntelEvent]:
        return self._events[-limit:]
