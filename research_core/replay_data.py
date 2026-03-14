from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ReplayStream:
    steps: list[datetime]
    aligned: dict[datetime, dict[str, Any]]
    divergences: list[str]


def align_inputs_to_step_ts(step_ts: list[datetime], streams: dict[str, list[dict[str, Any]]]) -> dict[datetime, dict[str, Any]]:
    aligned: dict[datetime, dict[str, Any]] = {}
    sorted_streams = {k: sorted(v, key=lambda r: r["ts"]) for k, v in streams.items()}
    for ts in step_ts:
        snapshot: dict[str, Any] = {}
        for name, records in sorted_streams.items():
            valid = [r for r in records if r["ts"] <= ts]
            snapshot[name] = valid[-1] if valid else None
        aligned[ts] = snapshot
    return aligned


def validate_replay_completeness(aligned: dict[datetime, dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for ts, payload in aligned.items():
        if payload.get("market_intel") is None:
            warnings.append(f"{ts.isoformat()}:missing_market_intel")
        if payload.get("events") is None:
            warnings.append(f"{ts.isoformat()}:missing_event_state")
        if payload.get("execution") is None:
            warnings.append(f"{ts.isoformat()}:missing_execution")
    return warnings


def load_replay_stream(step_ts: list[datetime], streams: dict[str, list[dict[str, Any]]]) -> ReplayStream:
    aligned = align_inputs_to_step_ts(step_ts, streams)
    divergences = validate_replay_completeness(aligned)
    return ReplayStream(steps=sorted(step_ts), aligned=aligned, divergences=divergences)
