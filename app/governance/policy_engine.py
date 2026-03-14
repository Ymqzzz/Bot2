from __future__ import annotations


def policy_check(
    spread_pctile: float,
    dislocation: float,
    near_event: bool,
    max_spread_pctile: float,
    dislocation_limit: float = 1.7,
) -> tuple[bool, str]:
    spread_pctile = float(spread_pctile)
    dislocation = float(dislocation)
    max_spread_pctile = float(max_spread_pctile)

    event_spread_cap = max(45.0, max_spread_pctile - 15.0)
    if near_event and spread_pctile > event_spread_cap:
        return False, "event_spread_policy_block"

    if spread_pctile > max_spread_pctile:
        return False, "spread_policy_block"

    # In stressed environments we tighten dislocation tolerance based on spread stress.
    spread_stress = max(0.0, (spread_pctile - 60.0) / 40.0)
    adaptive_dislocation_limit = max(0.9, dislocation_limit - (0.35 * spread_stress))
    if dislocation > adaptive_dislocation_limit:
        return False, "dislocation_policy_block"

    if near_event and dislocation > 1.2:
        return False, "event_dislocation_block"
    return True, ""
