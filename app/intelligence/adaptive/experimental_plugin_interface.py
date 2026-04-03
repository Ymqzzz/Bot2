from __future__ import annotations

from typing import Protocol


class ExperimentalPluginInterface(Protocol):
    name: str

    def evaluate(self, features: dict[str, float], context: dict) -> float:
        ...
