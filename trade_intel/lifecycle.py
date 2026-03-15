from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .models import TradeLifecycleRecord


class TradeLifecycleManager:
    def __init__(self):
        self._records: dict[str, TradeLifecycleRecord] = {}

    def register_planned_trade(self, record: TradeLifecycleRecord) -> None:
        self._records[record.fingerprint.trade_id] = replace(record, status="planned")

    def register_open_trade(self, trade_id: str, entry_filled: float) -> TradeLifecycleRecord | None:
        rec = self._records.get(trade_id)
        if not rec:
            return None
        rec.fingerprint.entry_filled = entry_filled
        rec.fingerprint.entry_ts = datetime.now(timezone.utc)
        rec.status = "opened"
        rec.opened_ts = datetime.now(timezone.utc)
        return rec

    def update_open_trade(self, trade_id: str, updates: dict[str, Any]) -> TradeLifecycleRecord | None:
        rec = self._records.get(trade_id)
        if not rec:
            return None
        rec.status = updates.get("status", rec.status)
        return rec

    def register_partial_exit(self, trade_id: str) -> TradeLifecycleRecord | None:
        rec = self._records.get(trade_id)
        if rec:
            rec.status = "partially_closed"
        return rec

    def close_trade(self, trade_id: str) -> TradeLifecycleRecord | None:
        rec = self._records.get(trade_id)
        if rec:
            rec.status = "closed"
            rec.closed_ts = datetime.now(timezone.utc)
        return rec

    def get_open_trade_record(self, trade_id: str) -> TradeLifecycleRecord | None:
        return self._records.get(trade_id)
