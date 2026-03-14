from __future__ import annotations


class KillSwitch:
    def __init__(self):
        self._active = False
        self._reason = ""

    def activate(self, reason: str) -> None:
        self._active = True
        self._reason = reason

    def deactivate(self) -> None:
        self._active = False
        self._reason = ""

    def status(self) -> tuple[bool, str]:
        return self._active, self._reason
