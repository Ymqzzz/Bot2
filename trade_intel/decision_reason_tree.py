from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DecisionReasonTree:
    """Deterministic reason ordering for auditability."""

    def order_rejections(self, reasons: list[str]) -> list[str]:
        priority = {
            "HEALTH_CIRCUIT_BREAKER": 0,
            "DECISION_NEGATIVE_EDGE": 1,
            "DECISION_DOWNSIDE_TOO_HIGH": 2,
            "DECISION_UNCERTAINTY_TOO_HIGH": 3,
            "DECISION_EXECUTION_QUALITY_LOW": 4,
            "DECISION_TRANSITION_RISK_HIGH": 5,
            "DECISION_SIGNAL_CONFLICT": 6,
        }
        return sorted(reasons, key=lambda r: priority.get(r, 99))
