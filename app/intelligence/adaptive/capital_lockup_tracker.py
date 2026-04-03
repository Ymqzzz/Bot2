from __future__ import annotations


class CapitalLockupTracker:
    """Tracks current and projected capital lockup by strategy family."""

    def aggregate_lockup(self, lockups: dict[str, float]) -> tuple[float, dict[str, float]]:
        normalized = {k: max(0.0, float(v)) for k, v in lockups.items()}
        return sum(normalized.values()), normalized

    def incremental_share(self, family: str, incremental: float, lockups: dict[str, float]) -> float:
        total = sum(lockups.values()) + max(0.0, incremental)
        if total <= 0.0:
            return 0.0
        return (lockups.get(family, 0.0) + max(0.0, incremental)) / total
