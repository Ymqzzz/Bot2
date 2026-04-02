from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelHealth:
    loaded: bool
    stale_days: int
    failed_inferences: int

    @property
    def healthy(self) -> bool:
        return self.loaded and self.stale_days <= 30 and self.failed_inferences < 5
