from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptiveScoreBreakdown:
    capital_component: float
    thesis_component: float
    negotiation_component: float
    path_component: float
    adversary_component: float
    memory_component: float

    @property
    def total(self) -> float:
        return (
            self.capital_component
            + self.thesis_component
            + self.negotiation_component
            + self.path_component
            + self.adversary_component
            + self.memory_component
        )


def build_confidence_breakdown(
    *,
    capital_efficiency: float,
    thesis_expectancy: float,
    negotiation_penalty: float,
    path_decay: float,
    adversary_fragility: float,
    memory_penalty: float,
) -> AdaptiveScoreBreakdown:
    return AdaptiveScoreBreakdown(
        capital_component=capital_efficiency * 0.08,
        thesis_component=thesis_expectancy * 0.06,
        negotiation_component=-negotiation_penalty * 0.12,
        path_component=-path_decay * 0.10,
        adversary_component=-adversary_fragility * 0.08,
        memory_component=-memory_penalty,
    )
