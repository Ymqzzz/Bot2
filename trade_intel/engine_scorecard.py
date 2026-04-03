from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EngineScore:
    engine: str
    trust: float = 0.5
    samples: int = 0
    expectancy: float = 0.0
    calibration_error: float = 0.0


@dataclass(slots=True)
class EngineScorecard:
    scores: dict[str, EngineScore] = field(default_factory=dict)

    def get(self, engine: str) -> EngineScore:
        if engine not in self.scores:
            self.scores[engine] = EngineScore(engine=engine)
        return self.scores[engine]
