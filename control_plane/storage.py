from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ControlPlaneStorage:
    def __init__(self, jsonl_path: str = "control_plane_decisions.jsonl", sqlite_path: str | None = "control_plane.db"):
        self.jsonl_path = Path(jsonl_path)
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        if self.sqlite_path:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(self.sqlite_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS control_regime_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, asof_ts TEXT, instrument TEXT, payload_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS control_event_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, asof_ts TEXT, payload_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS control_execution_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, asof_ts TEXT, candidate_id TEXT, instrument TEXT, payload_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS control_allocation_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, asof_ts TEXT, payload_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS control_portfolio_state_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, asof_ts TEXT, payload_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS control_order_tactic_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, asof_ts TEXT, candidate_id TEXT, instrument TEXT, payload_json TEXT)")
        conn.commit()
        conn.close()

    def append_jsonl(self, record_type: str, payload: dict[str, Any]) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": record_type, "payload": payload}, sort_keys=True) + "\n")

    def persist(self, record_type: str, payload: dict[str, Any], candidate_id: str | None = None, instrument: str | None = None) -> None:
        self.append_jsonl(record_type, payload)
        if not self.sqlite_path:
            return
        conn = sqlite3.connect(self.sqlite_path)
        cur = conn.cursor()
        asof = payload.get("asof") or payload.get("asof_ts")
        pjson = json.dumps(payload, sort_keys=True)
        table = {
            "regime": "control_regime_decisions",
            "event": "control_event_decisions",
            "execution": "control_execution_decisions",
            "allocation": "control_allocation_decisions",
            "portfolio": "control_portfolio_state_snapshots",
            "tactic": "control_order_tactic_plans",
        }[record_type]
        cols = ["asof_ts", "payload_json"]
        vals: list[Any] = [asof, pjson]
        if table in {"control_regime_decisions", "control_execution_decisions", "control_order_tactic_plans"}:
            cols.insert(1, "instrument")
            vals.insert(1, instrument)
        if table in {"control_execution_decisions", "control_order_tactic_plans"}:
            cols.insert(1, "candidate_id")
            vals.insert(1, candidate_id)
        q = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['?']*len(vals))})"
        cur.execute(q, vals)
        conn.commit()
        conn.close()
