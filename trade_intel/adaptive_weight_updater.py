from __future__ import annotations

from dataclasses import dataclass, field

from .contextual_weight_memory import ContextualWeightMemory
from .engine_scorecard import EngineScorecard
from .performance_decay_model import PerformanceDecayModel


@dataclass(slots=True)
class AdaptiveWeightUpdater:
    alpha: float = 0.15
    min_trust: float = 0.1
    max_trust: float = 0.95
    decay: PerformanceDecayModel = field(default_factory=PerformanceDecayModel)
    memory: ContextualWeightMemory = field(default_factory=ContextualWeightMemory)

    def update(
        self,
        scorecard: EngineScorecard,
        engine: str,
        realized_r: float,
        predicted_edge: float,
        regime: str = "unknown",
        session: str = "unknown",
        instrument: str = "unknown",
    ) -> float:
        row = scorecard.get(engine)
        row.samples += 1
        row.expectancy = self.decay.ewma(row.expectancy, realized_r)
        error = abs(realized_r - predicted_edge)
        row.calibration_error = self.decay.ewma(row.calibration_error, error)

        if realized_r > 0 and error < 0.8:
            row.trust += 0.04
        elif realized_r < 0:
            row.trust -= 0.05
        row.trust = max(self.min_trust, min(self.max_trust, row.trust))
        contextual = self.memory.get(engine, regime, session, instrument)
        merged = 0.7 * row.trust + 0.3 * contextual
        self.memory.update(engine, regime, session, instrument, merged)
        return merged
