from __future__ import annotations

import logging

logger = logging.getLogger("control_plane")


def emit_control_event(event_type: str, payload: dict) -> None:
    logger.info("[CONTROL_EVENT] %s %s", event_type, payload)
