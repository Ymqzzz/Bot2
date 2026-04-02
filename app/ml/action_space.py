from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class MetaAction(IntEnum):
    VETO_TRADE = 0
    ALLOW_AS_IS = 1
    REDUCE_SIZE_25 = 2
    REDUCE_SIZE_50 = 3
    INCREASE_SIZE_25_WITHIN_CAPS = 4
    DELAY_AND_RECHECK = 5
    REQUIRE_HIGHER_CONFIRMATION = 6
    FORCE_FLAT_ON_WEAK_THESIS = 7


@dataclass(frozen=True)
class ActionMask:
    allowed: tuple[bool, ...]


def valid_actions(has_candidate: bool, in_position: bool, risk_deterioration: bool) -> ActionMask:
    allowed = [False] * len(MetaAction)
    if has_candidate:
        for i in range(0, 7):
            allowed[i] = True
        allowed[MetaAction.FORCE_FLAT_ON_WEAK_THESIS] = in_position
    else:
        allowed[MetaAction.ALLOW_AS_IS] = True
        allowed[MetaAction.DELAY_AND_RECHECK] = True
        allowed[MetaAction.FORCE_FLAT_ON_WEAK_THESIS] = in_position and risk_deterioration
    return ActionMask(tuple(allowed))


def ensure_valid(action: int, mask: ActionMask) -> int:
    if action < 0 or action >= len(mask.allowed) or not mask.allowed[action]:
        for idx, is_allowed in enumerate(mask.allowed):
            if is_allowed:
                return idx
        return int(MetaAction.ALLOW_AS_IS)
    return action
