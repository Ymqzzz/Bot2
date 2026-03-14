from __future__ import annotations

from typing import Protocol

from app.models.schema import SignalCandidate


class StrategyPlugin(Protocol):
    def name(self) -> str:
        ...

    def generate(self, instrument: str, bars: list[dict], features: dict) -> SignalCandidate | None:
        ...
