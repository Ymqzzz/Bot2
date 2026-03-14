from __future__ import annotations


def policy_check(
    spread_pctile: float,
    dislocation: float,
    near_event: bool,
    max_spread_pctile: float,
    dislocation_limit: float = 1.7,
) -> tuple[bool, str]:
    if spread_pctile > max_spread_pctile:
        return False, "spread_policy_block"
    if dislocation > dislocation_limit:
        return False, "dislocation_policy_block"
    if near_event and dislocation > 1.2:
        return False, "event_dislocation_block"
    return True, ""
