from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EdgeThresholdModel:
    base_min_edge: float = 0.05

    def min_edge(self, instrument: str, session_name: str) -> float:
        min_edge = self.base_min_edge
        if session_name.upper() in {"ASIA", "POST_CLOSE"}:
            min_edge += 0.03
        if instrument.upper().endswith("JPY"):
            min_edge += 0.01
        if instrument.upper() in {"BTC_USD", "ETH_USD"}:
            min_edge += 0.04
        return min_edge

    def max_uncertainty(self, session_name: str) -> float:
        if session_name.upper() in {"LONDON", "NY"}:
            return 0.55
        return 0.45
