from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BotEvent:
    event_type: str
    trace_id: str
    payload: dict[str, Any]
    ts: str = field(default_factory=utc_now_iso)


class EventBus:
    def __init__(self):
        self.events: list[BotEvent] = []

    def new_trace(self) -> str:
        return str(uuid.uuid4())

    def emit(self, event_type: str, trace_id: str, payload: dict[str, Any]) -> BotEvent:
        ev = BotEvent(event_type=event_type, trace_id=trace_id, payload=payload)
        self.events.append(ev)
        return ev
