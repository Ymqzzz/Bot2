from __future__ import annotations


def data_age_seconds(now_ts: int, data_ts: int) -> int:
    age = int(now_ts) - int(data_ts)
    return max(0, age)
