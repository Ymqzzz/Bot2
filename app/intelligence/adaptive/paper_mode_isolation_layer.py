from __future__ import annotations


class PaperModeIsolationLayer:
    def sanitize(self, result: dict[str, float]) -> dict[str, float]:
        sanitized = dict(result)
        sanitized["live_ordering_allowed"] = 0.0
        return sanitized
