from __future__ import annotations

import json
import sqlite3

from market_intel.pipeline import MarketIntelPipeline
from market_intel.replay import ReplayFrame, validate_deterministic_replay
from market_intel.storage import SnapshotStorage, flatten_features


def test_flatten_features_nested():
    nested = {"a": {"b": 1, "c": [{"d": 2}, 3]}, "z": 4}
    got = flatten_features(nested)
    assert got == {
        "a.b": 1,
        "a.c.0.d": 2,
        "a.c.1": 3,
        "z": 4,
    }


def test_pipeline_persists_jsonl_and_sqlite(tmp_path):
    jsonl = tmp_path / "snapshots.jsonl"
    sqlite_path = tmp_path / "snapshots.db"
    storage = SnapshotStorage(jsonl_path=str(jsonl), sqlite_path=str(sqlite_path))
    pipeline = MarketIntelPipeline(storage=storage)

    snapshot = pipeline.build_snapshot(
        timestamp="2026-01-01T00:00:00Z",
        instrument="EUR_USD",
        bars=[{"close": 1.1, "volume": 10}, {"close": 1.2, "volume": 12}],
        ticks=[{"bid": 1.2, "ask": 1.2001}],
        provider_statuses={"fx_feed": {"status": "ok", "latency_ms": 12.0}},
    )

    assert snapshot["summary_scores"]["provider_availability"] == 1.0
    lines = [json.loads(x) for x in jsonl.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    assert lines[0]["flattened_features"]["bar_count"] == 2

    with sqlite3.connect(str(sqlite_path)) as conn:
        snap_count = conn.execute("SELECT COUNT(*) FROM market_intel_snapshots").fetchone()[0]
        provider_count = conn.execute("SELECT COUNT(*) FROM market_intel_provider_status").fetchone()[0]
    assert snap_count == 1
    assert provider_count == 1


def test_replay_deterministic_for_same_stream():
    pipeline = MarketIntelPipeline()
    frames = [
        ReplayFrame(
            timestamp="2026-01-01T00:00:00Z",
            instrument="EUR_USD",
            bars=({"close": 1.1, "volume": 10},),
            ticks=({"bid": 1.1, "ask": 1.1001},),
            provider_statuses={"fx_feed": {"status": "ok", "latency_ms": 10}},
        ),
        ReplayFrame(
            timestamp="2026-01-01T00:00:01Z",
            instrument="EUR_USD",
            bars=({"close": 1.2, "volume": 11},),
            ticks=({"bid": 1.2, "ask": 1.2001},),
            provider_statuses={"fx_feed": {"status": "ok", "latency_ms": 11}},
        ),
    ]

    assert validate_deterministic_replay(pipeline, frames, config={"mode": "test"})
