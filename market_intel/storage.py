from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def flatten_features(payload: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in sorted(payload.keys()):
        value = payload[key]
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            out.update(flatten_features(value, parent_key=new_key, sep=sep))
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                list_key = f"{new_key}{sep}{idx}"
                if isinstance(item, dict):
                    out.update(flatten_features(item, parent_key=list_key, sep=sep))
                else:
                    out[list_key] = item
        else:
            out[new_key] = value
    return out


class SnapshotStorage:
    def __init__(self, jsonl_path: str = "research_outputs/market_intel_snapshots.jsonl", sqlite_path: str | None = None):
        self.jsonl_path = Path(jsonl_path)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path
        if self.sqlite_path:
            self._ensure_sqlite_schema()

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _ensure_sqlite_schema(self) -> None:
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_intel_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_ts TEXT,
                    instrument TEXT,
                    snapshot_hash TEXT UNIQUE,
                    snapshot_json TEXT NOT NULL,
                    flattened_features_json TEXT NOT NULL,
                    summary_scores_json TEXT NOT NULL,
                    usability_flags_json TEXT NOT NULL,
                    provider_statuses_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_intel_provider_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    status TEXT,
                    latency_ms REAL,
                    payload_json TEXT,
                    FOREIGN KEY(snapshot_id) REFERENCES market_intel_snapshots(id)
                )
                """
            )

    def persist(
        self,
        *,
        snapshot: dict[str, Any],
        features: dict[str, Any],
        summary_scores: dict[str, Any],
        provider_statuses: dict[str, Any],
        usability_flags: dict[str, Any],
    ) -> dict[str, Any]:
        flattened = flatten_features(features)
        record = {
            "snapshot": snapshot,
            "flattened_features": flattened,
            "summary_scores": summary_scores,
            "provider_statuses": provider_statuses,
            "usability_flags": usability_flags,
        }
        record["snapshot_hash"] = self._digest(record)

        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

        if self.sqlite_path:
            self._persist_sqlite(record)
        return record

    def _persist_sqlite(self, record: dict[str, Any]) -> None:
        assert self.sqlite_path is not None
        snapshot = record.get("snapshot", {})
        with sqlite3.connect(self.sqlite_path) as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO market_intel_snapshots(
                    snapshot_ts, instrument, snapshot_hash, snapshot_json,
                    flattened_features_json, summary_scores_json,
                    usability_flags_json, provider_statuses_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(snapshot.get("timestamp", "")),
                    str(snapshot.get("instrument", "")),
                    record["snapshot_hash"],
                    json.dumps(record["snapshot"], sort_keys=True),
                    json.dumps(record["flattened_features"], sort_keys=True),
                    json.dumps(record["summary_scores"], sort_keys=True),
                    json.dumps(record["usability_flags"], sort_keys=True),
                    json.dumps(record["provider_statuses"], sort_keys=True),
                ),
            )
            if cur.rowcount <= 0:
                return
            snapshot_id = cur.lastrowid
            for provider, status_payload in sorted(record["provider_statuses"].items()):
                status_payload = status_payload or {}
                conn.execute(
                    """
                    INSERT INTO market_intel_provider_status(snapshot_id, provider, status, latency_ms, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        provider,
                        str(status_payload.get("status", "")),
                        float(status_payload.get("latency_ms", 0.0) or 0.0),
                        json.dumps(status_payload, sort_keys=True),
                    ),
                )
from typing import Dict, Optional, Tuple

from .models import MarketIntelSnapshot


class InMemorySnapshotStore:
    def __init__(self) -> None:
        self._data: Dict[Tuple[str, str], MarketIntelSnapshot] = {}

    def put(self, snapshot: MarketIntelSnapshot) -> None:
        key = (snapshot.session.instrument, snapshot.session.asof.isoformat())
        self._data[key] = snapshot

    def get(self, instrument: str, asof_iso: str) -> Optional[MarketIntelSnapshot]:
        return self._data.get((instrument, asof_iso))
