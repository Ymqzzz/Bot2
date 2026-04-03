from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class AdaptiveStatefulMemory:
    maxlen: int = 200
    _history: deque[dict] = field(default_factory=deque)

    def push(self, entry: dict) -> None:
        if self._history.maxlen != self.maxlen:
            self._history = deque(self._history, maxlen=self.maxlen)
        self._history.append(dict(entry))

    def recent_fail_rate(self, window: int = 20) -> float:
        if not self._history:
            return 0.0
        items = list(self._history)[-window:]
        if not items:
            return 0.0
        fails = sum(1 for item in items if not bool(item.get("approved", False)))
        return fails / len(items)

    def recent_fragility_avg(self, window: int = 20) -> float:
        items = list(self._history)[-window:]
        if not items:
            return 0.0
        return sum(float(item.get("adversary_fragility", 0.0)) for item in items) / len(items)
