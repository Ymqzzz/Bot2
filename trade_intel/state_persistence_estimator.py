from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StatePersistenceEstimate:
    current_run_length: int
    dominant_state: str
    dominant_fraction: float
    persistence_score: float


class StatePersistenceEstimator:
    def estimate(self, regimes: list[str]) -> StatePersistenceEstimate:
        if not regimes:
            return StatePersistenceEstimate(0, "unknown", 0.0, 0.0)

        dominant_state = max(set(regimes), key=regimes.count)
        dominant_fraction = regimes.count(dominant_state) / len(regimes)

        current = regimes[-1]
        run = 1
        for idx in range(len(regimes) - 2, -1, -1):
            if regimes[idx] != current:
                break
            run += 1

        persistence = min(1.0, 0.65 * dominant_fraction + 0.35 * (run / len(regimes)))
        return StatePersistenceEstimate(run, dominant_state, dominant_fraction, persistence)
