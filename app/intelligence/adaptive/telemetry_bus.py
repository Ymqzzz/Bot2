from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AdaptiveTelemetryBus:
    """In-memory telemetry sink used to keep adaptive evaluations inspectable in tests/replay."""

    _events: list[dict] = field(default_factory=list)

    def emit(self, payload: dict) -> None:
        self._events.append(dict(payload))

    def recent(self, limit: int = 10) -> list[dict]:
        if limit <= 0:
            return []
        return self._events[-limit:]

    def clear(self) -> None:
        self._events.clear()
