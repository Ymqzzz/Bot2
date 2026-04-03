from __future__ import annotations


class ExpectancyDecayTracker:
    def slope(self, expectancy_history: list[float]) -> float:
        if len(expectancy_history) < 2:
            return 0.0
        return (expectancy_history[-1] - expectancy_history[0]) / max(1, len(expectancy_history) - 1)
