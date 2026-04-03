from __future__ import annotations

from app.intelligence.base import clamp


class OpportunityCostAllocator:
    """Penalizes trades that consume scarce capital while offering weak edge."""

    def penalty(self, *, expected_edge: float, incremental_margin: float, queue: list[dict]) -> float:
        if incremental_margin <= 0:
            return 0.0
        edge_per_margin = expected_edge / incremental_margin
        competing = [float(c.get("expected_edge", 0.0)) / max(float(c.get("incremental_margin", 1.0)), 1e-9) for c in queue]
        if not competing:
            return 0.0
        benchmark = max(competing)
        if benchmark <= 0.0:
            return 0.0
        return clamp((benchmark - edge_per_margin) / benchmark)
