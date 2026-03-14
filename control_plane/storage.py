from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class ControlPlaneStorage:
    def __init__(self, base_path: str = "control_plane_logs", sqlite_path: str | None = None) -> None:
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path
        self.conn = sqlite3.connect(sqlite_path) if sqlite_path else None
        if self.conn:
            self._init_tables()

    def _init_tables(self) -> None:
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS control_regime_decisions(id INTEGER PRIMARY KEY, asof_ts TEXT, instrument TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS control_event_decisions(id INTEGER PRIMARY KEY, asof_ts TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS control_execution_decisions(id INTEGER PRIMARY KEY, asof_ts TEXT, candidate_id TEXT, instrument TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS control_allocation_decisions(id INTEGER PRIMARY KEY, asof_ts TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS control_order_tactic_plans(id INTEGER PRIMARY KEY, asof_ts TEXT, candidate_id TEXT, instrument TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS control_portfolio_state_snapshots(id INTEGER PRIMARY KEY, asof_ts TEXT, payload_json TEXT)")
        self.conn.commit()

    def append_jsonl(self, name: str, row: dict) -> None:
        with (self.base / f"{name}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
