from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class WalkForwardResult:
    fold_scores: list[float]

    @property
    def mean_score(self) -> float:
        if not self.fold_scores:
            return 0.0
        return sum(self.fold_scores) / len(self.fold_scores)


def run_walk_forward(folds: list[tuple[list[float], list[float]]], trainer: Callable[[list[float], list[float]], float]) -> WalkForwardResult:
    scores = [float(trainer(train, test)) for train, test in folds]
    return WalkForwardResult(fold_scores=scores)
