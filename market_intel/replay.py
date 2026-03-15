from __future__ import annotations

from typing import Iterable, List

from .models import MarketIntelSnapshot


class MarketIntelReplay:
    def __init__(self, snapshots: Iterable[MarketIntelSnapshot]) -> None:
        self._snapshots: List[MarketIntelSnapshot] = list(snapshots)

    def iter_snapshots(self) -> Iterable[MarketIntelSnapshot]:
        return iter(self._snapshots)
