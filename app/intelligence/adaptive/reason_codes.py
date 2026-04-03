from __future__ import annotations

from enum import Enum


class AdaptiveReasonCode(str, Enum):
    CAPITAL_EFFICIENT = "ADAPTIVE_CAPITAL_EFFICIENT"
    MARGIN_COMPRESSED = "ADAPTIVE_MARGIN_COMPRESSED"
    OPPORTUNITY_COST_HIGH = "ADAPTIVE_OPPORTUNITY_COST_HIGH"
    LIQUIDATION_CASCADE_RISK = "ADAPTIVE_LIQUIDATION_CASCADE_RISK"
    NEGOTIATION_VETO = "ADAPTIVE_NEGOTIATION_VETO"
    PATH_CHAOTIC = "ADAPTIVE_PATH_CHAOTIC"
    EDGE_DECAY = "ADAPTIVE_EDGE_DECAY"
    ADVERSARY_FRAGILE = "ADAPTIVE_ADVERSARY_FRAGILE"
    RETRY_ALLOWED = "ADAPTIVE_RETRY_ALLOWED"
    EXECUTION_MEMORY_PENALTY = "ADAPTIVE_EXECUTION_MEMORY_PENALTY"


def map_capital_reasons(reasons: list[str]) -> list[AdaptiveReasonCode]:
    mapped: list[AdaptiveReasonCode] = []
    for reason in reasons:
        if reason == "CAPITAL_EFFICIENT":
            mapped.append(AdaptiveReasonCode.CAPITAL_EFFICIENT)
        elif reason == "MARGIN_HEADROOM_COMPRESSED":
            mapped.append(AdaptiveReasonCode.MARGIN_COMPRESSED)
        elif reason == "OPPORTUNITY_COST_HIGH":
            mapped.append(AdaptiveReasonCode.OPPORTUNITY_COST_HIGH)
        elif reason == "LIQUIDATION_CASCADE_RISK":
            mapped.append(AdaptiveReasonCode.LIQUIDATION_CASCADE_RISK)
    return mapped
