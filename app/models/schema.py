from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignalCandidate:
    instrument: str
    side: str
    score: float
    strategy: str
    entry_price: float
    stop_loss: float
    take_profit: float
    metadata: dict
