from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class _Entry:
    value: Any
    expires_at: datetime


class TTLCache:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._data: Dict[str, _Entry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if entry is None:
            return None
        if datetime.utcnow() >= entry.expires_at:
            self._data.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = _Entry(value=value, expires_at=datetime.utcnow() + self._ttl)
