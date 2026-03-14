from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class NormalizedEvent:
    event_id: str
    title: str
    currency: str
    impact: str
    scheduled_ts: datetime
    event_type: str
    source: str
    fresh: bool
    revision_risk: bool


def classify_event_type(title: str) -> str:
    t = title.upper()
    if "POWELL" in t:
        return "POWELL"
    if "FOMC" in t or "RATE DECISION" in t:
        return "FOMC"
    if "NFP" in t or "NONFARM" in t:
        return "NFP"
    if "UNEMPLOY" in t or "LABOR" in t:
        return "LABOR"
    if "CPI" in t:
        return "CPI"
    if "PPI" in t:
        return "PPI"
    if "GDP" in t:
        return "GDP"
    return "OTHER"


def normalize_events(raw_events: list[dict], source: str = "calendar") -> list[NormalizedEvent]:
    out: list[NormalizedEvent] = []
    now = datetime.now(timezone.utc)
    for i, e in enumerate(raw_events):
        when = e.get("scheduled_ts") or e.get("when") or e.get("time")
        if not when:
            continue
        if isinstance(when, datetime):
            ts = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        else:
            ts = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
        title = str(e.get("title") or e.get("event") or "")
        impact = str(e.get("impact") or "medium").lower()
        out.append(NormalizedEvent(
            event_id=str(e.get("event_id") or f"{source}-{i}"),
            title=title,
            currency=str(e.get("currency") or ""),
            impact=impact,
            scheduled_ts=ts,
            event_type=classify_event_type(title),
            source=str(e.get("source") or source),
            fresh=abs((ts - now).total_seconds()) <= 86400,
            revision_risk=bool(e.get("revision_risk", False)),
        ))
    return sorted(out, key=lambda x: (x.scheduled_ts, x.event_id))
