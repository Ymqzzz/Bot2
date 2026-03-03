from __future__ import annotations

from datetime import datetime, timezone


def session_playbook(session_name: str, focus: list, edge_mode: str):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session": session_name,
        "target_pairs": [f.get("instrument") for f in focus[:8]],
        "strategy_weights": {f.get("instrument"): f.get("confidence", 0.5) for f in focus[:8]},
        "risk_mode": edge_mode,
    }
