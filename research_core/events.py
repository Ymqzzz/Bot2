from __future__ import annotations

from datetime import datetime, timezone


def emit_event(event_name: str, payload: dict) -> dict:
    return {
        "event": event_name,
        "ts": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
