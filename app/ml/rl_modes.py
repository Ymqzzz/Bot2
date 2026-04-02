from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RLMode(str, Enum):
    SHADOW = "shadow"
    ADVISORY = "advisory"
    ACTIVE = "active"


@dataclass(frozen=True)
class ModeCapabilities:
    may_veto: bool
    may_resize: bool
    live_effect: bool


_CAPS = {
    RLMode.SHADOW: ModeCapabilities(may_veto=False, may_resize=False, live_effect=False),
    RLMode.ADVISORY: ModeCapabilities(may_veto=False, may_resize=True, live_effect=True),
    RLMode.ACTIVE: ModeCapabilities(may_veto=True, may_resize=True, live_effect=True),
}


def mode_capabilities(mode: RLMode) -> ModeCapabilities:
    return _CAPS[mode]
