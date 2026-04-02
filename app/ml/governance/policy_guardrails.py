from __future__ import annotations

from app.ml.action_space import MetaAction
from app.ml.rl_modes import RLMode, mode_capabilities


def apply_policy_constraints(action: int, mode: RLMode, hard_risk_blocked: bool) -> int:
    if hard_risk_blocked:
        return int(MetaAction.VETO_TRADE)
    caps = mode_capabilities(mode)
    if not caps.live_effect:
        return int(MetaAction.ALLOW_AS_IS)
    if not caps.may_veto and action == int(MetaAction.VETO_TRADE):
        return int(MetaAction.REQUIRE_HIGHER_CONFIRMATION)
    return action
