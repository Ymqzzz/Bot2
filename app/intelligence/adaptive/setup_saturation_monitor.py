from __future__ import annotations

from app.intelligence.base import clamp


class SetupSaturationMonitor:
    def saturation(self, *, trades_recent: int, baseline: int) -> float:
        if baseline <= 0:
            return 0.0
        return clamp(trades_recent / baseline)
