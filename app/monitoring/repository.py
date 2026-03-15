from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import json
import sqlite3
import threading
from typing import Any


NUMERIC_DIAGNOSTIC_KEYS = (
    "score",
    "dislocation",
    "slippage_bps",
    "expected_price",
    "filled_price",
    "qty",
    "size",
    "risk_pct",
)


@dataclass(frozen=True)
class DecisionFunnelCounts:
    signal_emitted: int
    signal_rejected: int
    risk_blocked: int
    order_submitted: int
    fill: int
    exit: int
    stop_updated: int


class BaseEventRepository:
    def persist_event(self, event: Any) -> None:
        raise NotImplementedError

    def candidate_counts(self, start_ts: str | None = None, end_ts: str | None = None) -> DecisionFunnelCounts:
        raise NotImplementedError

    def rejection_reasons(self, limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError

    def slippage_trends(self, instrument: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError


class SQLEventRepository(BaseEventRepository):
    """Storage-backed repository for lifecycle events.

    Supports SQLite and PostgreSQL DB-API connections via a minimal abstraction.
    """

    def __init__(
        self,
        *,
        dialect: str = "sqlite",
        sqlite_path: str = "research_outputs/monitoring/events.db",
        postgres_dsn: str | None = None,
    ):
        self.dialect = dialect
        self._lock = threading.Lock()
        if dialect == "sqlite":
            path = Path(sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path)
            self._conn.row_factory = sqlite3.Row
        elif dialect == "postgres":
            if not postgres_dsn:
                raise ValueError("postgres_dsn is required for postgres dialect")
            try:
                import psycopg

                self._conn = psycopg.connect(postgres_dsn)
            except ImportError:
                import psycopg2  # type: ignore

                self._conn = psycopg2.connect(postgres_dsn)
        else:
            raise ValueError(f"Unsupported dialect: {dialect}")
        self._init_schema()

    def _placeholder(self) -> str:
        return "%s" if self.dialect == "postgres" else "?"

    def _with_filters(self, base_sql: str, start_ts: str | None = None, end_ts: str | None = None, instrument: str | None = None) -> tuple[str, list[Any]]:
        params: list[Any] = []
        clauses: list[str] = []
        p = self._placeholder()
        if start_ts:
            clauses.append(f"ts >= {p}")
            params.append(start_ts)
        if end_ts:
            clauses.append(f"ts <= {p}")
            params.append(end_ts)
        if instrument:
            clauses.append(f"instrument = {p}")
            params.append(instrument)
        if clauses:
            if " where " in base_sql.lower():
                return base_sql + " AND " + " AND ".join(clauses), params
            return base_sql + " WHERE " + " AND ".join(clauses), params
        return base_sql, params

    def _init_schema(self) -> None:
        if self.dialect == "postgres":
            schema_sql = """
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                id BIGSERIAL PRIMARY KEY,
                trace_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                ts TIMESTAMPTZ NOT NULL,
                instrument TEXT,
                strategy TEXT,
                reason_code TEXT,
                score DOUBLE PRECISION,
                dislocation DOUBLE PRECISION,
                slippage_bps DOUBLE PRECISION,
                expected_price DOUBLE PRECISION,
                filled_price DOUBLE PRECISION,
                qty DOUBLE PRECISION,
                payload_json JSONB NOT NULL
            );
            """
            index_sql = [
                "CREATE INDEX IF NOT EXISTS idx_events_trace_id ON lifecycle_events(trace_id)",
                "CREATE INDEX IF NOT EXISTS idx_events_event_type_ts ON lifecycle_events(event_type, ts)",
                "CREATE INDEX IF NOT EXISTS idx_events_instrument_ts ON lifecycle_events(instrument, ts)",
                "CREATE INDEX IF NOT EXISTS idx_events_strategy_ts ON lifecycle_events(strategy, ts)",
                "CREATE INDEX IF NOT EXISTS idx_events_reason_code ON lifecycle_events(reason_code)",
            ]
        else:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                ts TEXT NOT NULL,
                instrument TEXT,
                strategy TEXT,
                reason_code TEXT,
                score REAL,
                dislocation REAL,
                slippage_bps REAL,
                expected_price REAL,
                filled_price REAL,
                qty REAL,
                payload_json TEXT NOT NULL
            );
            """
            index_sql = [
                "CREATE INDEX IF NOT EXISTS idx_events_trace_id ON lifecycle_events(trace_id)",
                "CREATE INDEX IF NOT EXISTS idx_events_event_type_ts ON lifecycle_events(event_type, ts)",
                "CREATE INDEX IF NOT EXISTS idx_events_instrument_ts ON lifecycle_events(instrument, ts)",
                "CREATE INDEX IF NOT EXISTS idx_events_strategy_ts ON lifecycle_events(strategy, ts)",
                "CREATE INDEX IF NOT EXISTS idx_events_reason_code ON lifecycle_events(reason_code)",
            ]
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(schema_sql)
            for stmt in index_sql:
                cur.execute(stmt)
            self._conn.commit()

    @staticmethod
    def _coerce_numeric(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _extract_row(self, event: Any) -> dict[str, Any]:
        payload = event.payload if isinstance(event.payload, Mapping) else {}
        reason_code = payload.get("reason_code") or payload.get("reason")
        diagnostics: dict[str, float | None] = {k: self._coerce_numeric(payload.get(k)) for k in NUMERIC_DIAGNOSTIC_KEYS}
        return {
            "trace_id": event.trace_id,
            "event_type": event.event_type,
            "ts": event.ts,
            "instrument": payload.get("instrument"),
            "strategy": payload.get("strategy"),
            "reason_code": reason_code,
            "score": diagnostics.get("score"),
            "dislocation": diagnostics.get("dislocation"),
            "slippage_bps": diagnostics.get("slippage_bps"),
            "expected_price": diagnostics.get("expected_price"),
            "filled_price": diagnostics.get("filled_price"),
            "qty": diagnostics.get("qty") or diagnostics.get("size"),
            "payload_json": json.dumps(payload, sort_keys=True),
        }

    def persist_event(self, event: Any) -> None:
        row = self._extract_row(event)
        p = self._placeholder()
        sql = f"""
        INSERT INTO lifecycle_events (
            trace_id, event_type, ts, instrument, strategy, reason_code,
            score, dislocation, slippage_bps, expected_price, filled_price, qty, payload_json
        ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """
        with self._lock:
            self._conn.execute(
                sql,
                (
                    row["trace_id"],
                    row["event_type"],
                    row["ts"],
                    row["instrument"],
                    row["strategy"],
                    row["reason_code"],
                    row["score"],
                    row["dislocation"],
                    row["slippage_bps"],
                    row["expected_price"],
                    row["filled_price"],
                    row["qty"],
                    row["payload_json"],
                ),
            )
            self._conn.commit()

    def candidate_counts(self, start_ts: str | None = None, end_ts: str | None = None) -> DecisionFunnelCounts:
        sql, params = self._with_filters(
            """
            SELECT
                SUM(CASE WHEN event_type = 'signal_emitted' THEN 1 ELSE 0 END) AS signal_emitted,
                SUM(CASE WHEN event_type = 'signal_rejected' THEN 1 ELSE 0 END) AS signal_rejected,
                SUM(CASE WHEN event_type = 'risk_blocked' THEN 1 ELSE 0 END) AS risk_blocked,
                SUM(CASE WHEN event_type = 'order_submitted' THEN 1 ELSE 0 END) AS order_submitted,
                SUM(CASE WHEN event_type = 'fill' THEN 1 ELSE 0 END) AS fill,
                SUM(CASE WHEN event_type = 'exit' THEN 1 ELSE 0 END) AS exit,
                SUM(CASE WHEN event_type IN ('stop_updated', 'stop_update') THEN 1 ELSE 0 END) AS stop_updated
            FROM lifecycle_events
            """,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        as_int = lambda x: int(x or 0)
        return DecisionFunnelCounts(
            signal_emitted=as_int(row[0]),
            signal_rejected=as_int(row[1]),
            risk_blocked=as_int(row[2]),
            order_submitted=as_int(row[3]),
            fill=as_int(row[4]),
            exit=as_int(row[5]),
            stop_updated=as_int(row[6]),
        )

    def rejection_reasons(self, limit: int = 20) -> list[dict[str, Any]]:
        p = self._placeholder()
        sql = f"""
            SELECT COALESCE(reason_code, 'unknown') AS reason_code, COUNT(*) AS n
            FROM lifecycle_events
            WHERE event_type IN ('signal_rejected', 'risk_blocked')
            GROUP BY COALESCE(reason_code, 'unknown')
            ORDER BY n DESC
            LIMIT {p}
        """
        rows = self._conn.execute(sql, (limit,)).fetchall()
        return [{"reason_code": r[0], "count": int(r[1])} for r in rows]

    def slippage_trends(self, instrument: str | None = None) -> list[dict[str, Any]]:
        if self.dialect == "postgres":
            bucket = "date_trunc('day', ts)"
        else:
            bucket = "substr(ts, 1, 10)"
        sql = f"""
            SELECT {bucket} AS bucket, AVG(slippage_bps) AS avg_slippage_bps, COUNT(*) AS fill_count
            FROM lifecycle_events
            WHERE event_type = 'fill' AND slippage_bps IS NOT NULL
        """
        sql, params = self._with_filters(sql, instrument=instrument)
        sql += " GROUP BY bucket ORDER BY bucket ASC"
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "bucket": str(r[0]),
                "avg_slippage_bps": float(r[1]),
                "fill_count": int(r[2]),
            }
            for r in rows
        ]


def create_event_repository(database_url: str | None = None) -> SQLEventRepository:
    """Create repository from URL.

    Supported URLs:
      - sqlite:///path/to/file.db
      - postgres://user:pass@host:port/db
      - postgresql://user:pass@host:port/db
    """
    if not database_url or database_url.startswith("sqlite://"):
        sqlite_path = database_url[len("sqlite:///") :] if database_url and database_url.startswith("sqlite:///") else "research_outputs/monitoring/events.db"
        return SQLEventRepository(dialect="sqlite", sqlite_path=sqlite_path)
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        return SQLEventRepository(dialect="postgres", postgres_dsn=database_url)
    raise ValueError(f"Unsupported database_url: {database_url}")
