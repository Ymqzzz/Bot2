from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Tuple

from .base import BaseTickProvider, ProviderResult


class TickSynthAdapter(BaseTickProvider):
    """Build pseudo second-level ticks from runtime mid/spread updates."""

    def __init__(self, max_updates: int = 4096) -> None:
        self._updates: Dict[str, Deque[Tuple[float, float, float]]] = defaultdict(lambda: deque(maxlen=max_updates))

    def ingest_update(self, instrument: str, *, mid: float, spread: float, ts: float | None = None) -> None:
        timestamp = float(ts if ts is not None else time.time())
        self._updates[instrument].append((timestamp, float(mid), float(spread)))

    def get_ticks(self, instrument: str, *, limit: int = 60) -> ProviderResult[List[dict]]:
        updates = list(self._updates[instrument])
        if not updates:
            return ProviderResult(ok=False, status="unavailable", source="tick_synth", error="No runtime updates")

        ticks: List[dict] = []
        for idx, (ts, mid, spread) in enumerate(updates):
            next_ts = updates[idx + 1][0] if idx + 1 < len(updates) else ts
            sec_end = max(int(ts), int(next_ts))
            for second in range(int(ts), sec_end + 1):
                ticks.append(
                    {
                        "time": datetime.fromtimestamp(second, tz=timezone.utc).isoformat(),
                        "mid": mid,
                        "bid": mid - spread / 2.0,
                        "ask": mid + spread / 2.0,
                        "spread": spread,
                        "source": "pseudo_tick",
                    }
                )

        ticks = ticks[-max(1, limit) :]
        return ProviderResult(ok=True, data=ticks, status="synthetic", source="tick_synth", meta={"is_true_tick": False})
