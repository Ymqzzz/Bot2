from __future__ import annotations

from datetime import datetime


EVENT_TYPE_MAP = {
    "CPI": "CPI", "NFP": "NFP", "PAYROLL": "NFP", "FOMC": "FOMC", "POWELL": "POWELL", "GDP": "GDP",
    "PPI": "PPI", "UNEMPLOYMENT": "LABOR", "LABOR": "LABOR", "BOE": "CENTRAL_BANK", "ECB": "CENTRAL_BANK", "BOJ": "CENTRAL_BANK", "RBA": "CENTRAL_BANK", "BOC": "CENTRAL_BANK",
}


def normalize_event(raw: dict) -> dict:
    title = str(raw.get("title") or raw.get("event") or "")
    up = title.upper()
    event_type = "OTHER"
    for key, value in EVENT_TYPE_MAP.items():
        if key in up:
            event_type = value
            break
    ts = raw.get("scheduled_ts") or raw.get("when") or raw.get("time")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return {
        "event_id": str(raw.get("event_id") or f"{raw.get('currency','XX')}-{int(ts.timestamp()) if hasattr(ts,'timestamp') else 0}"),
        "title": title,
        "currency": str(raw.get("currency") or ""),
        "impact": str(raw.get("impact") or "medium").lower(),
        "scheduled_ts": ts,
        "event_type": event_type,
        "source": str(raw.get("source") or "unknown"),
        "fresh": bool(raw.get("fresh", True)),
        "revision_risk": int(raw.get("revision_risk", 1)),
    }


def normalize_calendar(raw_events: list[dict]) -> list[dict]:
    out = [normalize_event(e) for e in raw_events]
    return sorted(out, key=lambda e: e["scheduled_ts"])
