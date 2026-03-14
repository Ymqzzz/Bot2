from __future__ import annotations

from app.models.schema import SignalCandidate


class StrategyRegistry:
    def __init__(self):
        self._plugins = []

    def register(self, plugin) -> None:
        self._plugins.append(plugin)

    @property
    def plugins(self):
        return list(self._plugins)

    def generate_candidates(self, instrument: str, bars: list[dict], features: dict) -> list[SignalCandidate]:
        out: list[SignalCandidate] = []
        for p in self._plugins:
            cand = p.generate(instrument=instrument, bars=bars, features=features)
            if cand is not None:
                out.append(cand)
        return out
