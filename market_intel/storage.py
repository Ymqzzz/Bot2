from __future__ import annotations

from typing import Dict, Optional, Tuple

from .models import MarketIntelSnapshot


class InMemorySnapshotStore:
    def __init__(self) -> None:
        self._data: Dict[Tuple[str, str], MarketIntelSnapshot] = {}

    def put(self, snapshot: MarketIntelSnapshot) -> None:
        key = (snapshot.session.instrument, snapshot.session.asof.isoformat())
        self._data[key] = snapshot

    def get(self, instrument: str, asof_iso: str) -> Optional[MarketIntelSnapshot]:
        return self._data.get((instrument, asof_iso))
