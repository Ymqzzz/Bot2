from __future__ import annotations


def clock_skew_ms(provider_ts_ms: int, local_ts_ms: int) -> int:
    return abs(int(provider_ts_ms) - int(local_ts_ms))
