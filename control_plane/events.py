from __future__ import annotations

from typing import Any


def emit_control_event(event_type: str, payload: dict[str, Any], sink: callable | None = None) -> None:
    event = {"event_type": event_type, "payload": payload}
    if sink:
        sink(event)
import logging

logger = logging.getLogger("control_plane")


def emit_control_event(event_type: str, payload: dict) -> None:
    logger.info("[CONTROL_EVENT] %s %s", event_type, payload)
