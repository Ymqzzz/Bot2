from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def write_eod_report(path: str, payload: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
