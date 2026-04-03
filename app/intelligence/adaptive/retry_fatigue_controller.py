from __future__ import annotations

from app.intelligence.base import clamp


class RetryFatigueController:
    def fatigue(self, retry_count: int) -> float:
        return clamp(retry_count / 4.0)
