from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass
class ModelRecord:
    model_id: str
    model_path: str
    training_config: dict
    feature_schema_hash: str
    normalization_stats_version: str
    windows: dict
    performance: dict
    created_at: str
    code_commit_hash: str
    reward_version: str
    backtest_report: str
    approved: bool


class ModelRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def register(self, record: ModelRecord) -> None:
        rows = self._read_all()
        rows = [r for r in rows if r["model_id"] != record.model_id]
        rows.append(asdict(record))
        self.path.write_text(json.dumps(rows, indent=2, sort_keys=True))

    def get_active(self) -> ModelRecord | None:
        rows = self._read_all()
        approved = [r for r in rows if r.get("approved")]
        if not approved:
            return None
        latest = max(approved, key=lambda r: r["created_at"])
        return ModelRecord(**latest)

    @staticmethod
    def draft_record(model_id: str, model_path: Path, **kwargs: dict) -> ModelRecord:
        now = datetime.now(tz=timezone.utc).isoformat()
        return ModelRecord(model_id=model_id, model_path=str(model_path), created_at=now, **kwargs)
