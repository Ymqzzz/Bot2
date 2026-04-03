from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ContextualWeightMemory:
    by_engine: dict[str, float] = field(default_factory=dict)
    by_engine_regime: dict[tuple[str, str], float] = field(default_factory=dict)
    by_engine_session: dict[tuple[str, str], float] = field(default_factory=dict)
    by_engine_instrument: dict[tuple[str, str], float] = field(default_factory=dict)

    def get(self, engine: str, regime: str, session: str, instrument: str) -> float:
        vals = [
            self.by_engine.get(engine, 0.5),
            self.by_engine_regime.get((engine, regime), 0.5),
            self.by_engine_session.get((engine, session), 0.5),
            self.by_engine_instrument.get((engine, instrument), 0.5),
        ]
        return sum(vals) / len(vals)

    def update(self, engine: str, regime: str, session: str, instrument: str, trust: float) -> None:
        self.by_engine[engine] = trust
        self.by_engine_regime[(engine, regime)] = trust
        self.by_engine_session[(engine, session)] = trust
        self.by_engine_instrument[(engine, instrument)] = trust
