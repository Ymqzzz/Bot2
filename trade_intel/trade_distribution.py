from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TradeDistribution:
    expected_return: float
    expected_downside: float
    expected_holding_time_sec: int
    fill_adjusted_alpha: float
    uncertainty: float
    confidence: float
    uncertainty_interval: tuple[float, float]
    raw_alpha: float
    spread_cost: float
    slippage_cost: float
    toxicity_penalty: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DecisionOutcome:
    approved: bool
    approval_status: str
    reason_codes: list[str] = field(default_factory=list)
    decline_reason_hierarchy: list[str] = field(default_factory=list)
    min_edge_required: float = 0.0
    transition_risk: float = 0.0
    execution_quality_estimate: float = 0.0
    size_multiplier_cap: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
