from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.adaptive.failure_mode_library import FAILURE_MODES


class AdversarialPathGenerator:
    def generate(self, *, attack_surface: float) -> list[tuple[str, float]]:
        ranked: list[tuple[str, float]] = []
        base = clamp(attack_surface)
        for idx, mode in enumerate(FAILURE_MODES):
            weight = clamp(base * (1.0 - idx * 0.08) + 0.1)
            ranked.append((mode, weight))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked
