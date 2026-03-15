from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import TradeIntelConfig


class TradeIntelStorage:
    def __init__(self, config: TradeIntelConfig):
        self.config = config
        self.path = Path(config.TRADE_INTEL_JSONL_PATH)
        self.sqlite_path = self.path.with_suffix(".sqlite")
        if config.TRADE_INTEL_SQLITE_ENABLED:
            self._init_sqlite()

    def append_jsonl(self, stream: str, payload: dict[str, Any]) -> None:
        if not self.config.TRADE_INTEL_STORAGE_ENABLED:
            return
        row = {"stream": stream, **payload}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(self.sqlite_path)
        cur = conn.cursor()
        for table in [
            "trade_fingerprints",
            "trade_entry_quality",
            "trade_path_metrics",
            "trade_exit_quality",
            "trade_outcome_attribution",
            "trade_sizing_decisions",
            "trade_exit_plans",
            "edge_health_snapshots",
            "trade_lifecycle_records",
            "trade_edge_snapshots",
            "trade_sizing_decisions",
            "trade_exit_plans",
            "trade_path_metrics",
        ]:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table}(id INTEGER PRIMARY KEY AUTOINCREMENT, trade_id TEXT, payload_json TEXT, created_at TEXT)")
        conn.commit()
        conn.close()

    def insert_sqlite(self, table: str, trade_id: str, payload: dict[str, Any]) -> None:
        if not self.config.TRADE_INTEL_SQLITE_ENABLED:
            return
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute(
            f"INSERT INTO {table}(trade_id,payload_json,created_at) VALUES(?,?,datetime('now'))",
            (trade_id, json.dumps(payload, default=str)),
        )
        conn.commit()
        conn.close()
