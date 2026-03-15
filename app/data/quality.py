from __future__ import annotations

from dataclasses import dataclass
from statistics import median
import time
from typing import Any


BLOCK_REASON_CODES = {
    "non_positive_price": "data_quality_non_positive_price",
    "timestamp_non_monotonic": "data_quality_timestamp_non_monotonic",
    "timestamp_duplicate": "data_quality_timestamp_duplicate",
    "bar_continuity_gap": "data_quality_bar_continuity_gap",
}

DEGRADE_REASON_CODES = {
    "stale_quotes": "data_quality_stale_quotes",
    "spread_outlier": "data_quality_spread_outlier",
}


@dataclass(frozen=True)
class DataQualityResult:
    instrument: str
    status: str
    failing_rules: list[str]
    reason_codes: list[str]


def _extract_ts(bar: dict[str, Any]) -> float | None:
    for key in ("timestamp", "ts", "time"):
        if key in bar and bar[key] is not None:
            return float(bar[key])
    return None


def _all_prices_positive(bars: list[dict[str, Any]]) -> bool:
    for bar in bars:
        for key in ("open", "high", "low", "close"):
            if float(bar.get(key, 0.0)) <= 0.0:
                return False
    return True


def validate_bars_quality(
    instrument: str,
    bars: list[dict[str, Any]],
    spread_pctile: float | None = None,
    now_ts: float | None = None,
) -> DataQualityResult:
    blocked: list[str] = []
    degraded: list[str] = []

    if not _all_prices_positive(bars):
        blocked.append("non_positive_price")

    timestamps = [_extract_ts(b) for b in bars]
    if all(ts is not None for ts in timestamps) and len(timestamps) >= 2:
        cast_ts = [float(ts) for ts in timestamps if ts is not None]
        seen: set[float] = set()
        duplicates = False
        non_mono = False
        deltas: list[float] = []
        for idx, ts in enumerate(cast_ts):
            if ts in seen:
                duplicates = True
            seen.add(ts)
            if idx > 0:
                delta = ts - cast_ts[idx - 1]
                if delta <= 0:
                    non_mono = True
                else:
                    deltas.append(delta)
        if duplicates:
            blocked.append("timestamp_duplicate")
        if non_mono:
            blocked.append("timestamp_non_monotonic")

        if deltas:
            med_delta = max(1.0, median(deltas))
            max_delta = max(deltas)
            if max_delta > (3.0 * med_delta):
                blocked.append("bar_continuity_gap")

            ref_now = float(now_ts if now_ts is not None else time.time())
            if ref_now - cast_ts[-1] > (4.0 * med_delta):
                degraded.append("stale_quotes")

    if spread_pctile is not None and spread_pctile >= 95.0:
        degraded.append("spread_outlier")

    blocked = sorted(set(blocked))
    degraded = sorted(set(degraded))

    if blocked:
        reasons = [BLOCK_REASON_CODES[r] for r in blocked]
        status = "blocked"
        failing = blocked + degraded
    elif degraded:
        reasons = [DEGRADE_REASON_CODES[r] for r in degraded]
        status = "degraded"
        failing = degraded
    else:
        reasons = []
        status = "pass"
        failing = []

    return DataQualityResult(
        instrument=instrument,
        status=status,
        failing_rules=failing,
        reason_codes=reasons,
    )
