from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .regime_conflict_resolver import RegimeConflictResolver
from .regime_instability_penalty import RegimeInstabilityPenaltyModel
from .state_persistence_estimator import StatePersistenceEstimator


@dataclass(slots=True)
class RegimeTransitionState:
    current_regime: str
    confidence: float
    transition_probability: dict[str, float]
    expected_duration: int
    instability_score: float
    transition_risk: float
    unsafe_for_trend: bool


@dataclass(slots=True)
class RegimeTransitionModel:
    window: int = 20
    _history: deque[str] = field(default_factory=lambda: deque(maxlen=20))
    persistence: StatePersistenceEstimator = field(default_factory=StatePersistenceEstimator)
    conflicts: RegimeConflictResolver = field(default_factory=RegimeConflictResolver)
    penalty: RegimeInstabilityPenaltyModel = field(default_factory=RegimeInstabilityPenaltyModel)

    def update(self, market_context: dict[str, Any]) -> RegimeTransitionState:
        regime = str(market_context.get("regime_name", "unknown"))
        confidence = max(0.0, min(1.0, float(market_context.get("regime_confidence", 0.5))))
        source_regimes = market_context.get("regime_sources", {})
        resolved = self.conflicts.resolve(source_regimes) if source_regimes else None
        if resolved:
            regime = resolved.resolved_regime
            confidence = 0.5 * confidence + 0.5 * resolved.confidence
        self._history.append(regime)
        switches = sum(1 for i in range(1, len(self._history)) if self._history[i] != self._history[i - 1])
        instability = switches / max(1, len(self._history) - 1)
        persistence = self.persistence.estimate(list(self._history))
        conflict_score = resolved.conflict_score if resolved else 0.0
        transition_risk = (1.0 - confidence) * 0.5 + instability * 0.3 + conflict_score * 0.2
        penalty = self.penalty.compute(transition_risk=transition_risk, persistence_score=persistence.persistence_score, conflict_score=conflict_score)
        expected_duration = max(1, int((1.0 - instability) * self.window))

        states = {"trend", "mean_reversion", "range", "volatile", "unknown"}
        transition_probability: dict[str, float] = {}
        if states:
            base = instability / len(states)
            for st in states:
                transition_probability[st] = base
            transition_probability[regime if regime in states else "unknown"] += max(0.0, 1.0 - instability)

        unsafe_for_trend = penalty.unsafe_for_trend
        return RegimeTransitionState(
            current_regime=regime,
            confidence=confidence,
            transition_probability=transition_probability,
            expected_duration=expected_duration,
            instability_score=max(instability, penalty.penalty),
            transition_risk=transition_risk,
            unsafe_for_trend=unsafe_for_trend,
        )
