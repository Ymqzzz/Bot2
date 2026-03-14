from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class AuditSink:
    def __init__(self, path: str = "research_outputs/audit_log.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def snapshot_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def append(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
