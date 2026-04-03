from __future__ import annotations


def should_trip(stale_seconds: int, nan_ratio: float, drift: float, hard_errors: int) -> bool:
    if hard_errors > 0:
        return True
    if stale_seconds > 240:
        return True
    if nan_ratio > 0.30:
        return True
    if drift > 0.85:
        return True
    return False
