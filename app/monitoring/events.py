from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from app.monitoring.repository import BaseEventRepository, DecisionFunnelCounts


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BotEvent:
    event_type: str
    trace_id: str
    payload: dict[str, Any]
    ts: str = field(default_factory=utc_now_iso)


class EventBus:
    def __init__(self, repository: BaseEventRepository | None = None, cache_size: int | None = 2_000):
        self.repository = repository
        self.cache_size = cache_size
        self.events: list[BotEvent] = []

    def new_trace(self) -> str:
        return str(uuid.uuid4())

    def emit(self, event_type: str, trace_id: str, payload: dict[str, Any]) -> BotEvent:
        ev = BotEvent(event_type=event_type, trace_id=trace_id, payload=payload)
        if self.repository is not None:
            self.repository.persist_event(ev)
        if self.cache_size is None or self.cache_size > 0:
            self.events.append(ev)
            if self.cache_size is not None and len(self.events) > self.cache_size:
                self.events.pop(0)
        return ev

    def candidate_counts(self, start_ts: str | None = None, end_ts: str | None = None) -> DecisionFunnelCounts:
        if self.repository is not None:
            return self.repository.candidate_counts(start_ts=start_ts, end_ts=end_ts)
        counts = {
            "signal_emitted": 0,
            "signal_rejected": 0,
            "risk_blocked": 0,
            "order_submitted": 0,
            "fill": 0,
            "exit": 0,
            "stop_updated": 0,
        }
        for ev in self.events:
            event_type = ev.event_type
            if event_type in counts:
                counts[event_type] += 1
            elif event_type == "stop_update":
                counts["stop_updated"] += 1
        return DecisionFunnelCounts(**counts)

    def rejection_reasons(self, limit: int = 20) -> list[dict[str, Any]]:
        if self.repository is not None:
            return self.repository.rejection_reasons(limit=limit)
        tally: dict[str, int] = {}
        for ev in self.events:
            if ev.event_type not in ("signal_rejected", "risk_blocked"):
                continue
            reason = str(ev.payload.get("reason_code") or ev.payload.get("reason") or "unknown")
            tally[reason] = tally.get(reason, 0) + 1
        return [
            {"reason_code": reason, "count": count}
            for reason, count in sorted(tally.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]

    def slippage_trends(self, instrument: str | None = None) -> list[dict[str, Any]]:
        if self.repository is not None:
            return self.repository.slippage_trends(instrument=instrument)
        grouped: dict[str, list[float]] = {}
        for ev in self.events:
            if ev.event_type != "fill":
                continue
            if instrument and ev.payload.get("instrument") != instrument:
                continue
            slippage_bps = ev.payload.get("slippage_bps")
            if not isinstance(slippage_bps, (int, float)):
                continue
            bucket = ev.ts[:10]
            grouped.setdefault(bucket, []).append(float(slippage_bps))
        rows = []
        for bucket in sorted(grouped):
            vals = grouped[bucket]
            rows.append({"bucket": bucket, "avg_slippage_bps": sum(vals) / len(vals), "fill_count": len(vals)})
        return rows
