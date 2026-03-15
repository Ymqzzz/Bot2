from __future__ import annotations

import hashlib

from app.research.replay_engine import ReplayEngine


class DeterministicIntelBot:
    def __init__(self, stale=False, missing=False):
        self.stale = stale
        self.missing = missing

    def run_cycle(self, _market_data, _broker_ctx):
        quality = 1.0
        fallback_flags = {"stale": self.stale, "missing": self.missing}
        if self.stale:
            quality -= 0.35
        if self.missing:
            quality -= 0.45
        quality = max(0.0, quality)

        snapshot = {
            "instrument": "EUR_USD",
            "liquidity_factor": 0.9 if not self.stale else 0.4,
            "fallback_flags": fallback_flags,
            "quality_score": quality,
        }
        approved = quality >= 0.4
        return [
            {
                "approved": approved,
                "reason": "quality_gate" if not approved else "ok",
                "snapshot": snapshot,
            }
        ]


def _snapshot_hash(snapshot: dict) -> str:
    return hashlib.sha1(repr(sorted(snapshot.items())).encode()).hexdigest()


def test_replay_is_deterministic_for_identical_snapshots():
    bot = DeterministicIntelBot(stale=False, missing=False)
    first = bot.run_cycle(None, None)[0]["snapshot"]
    second = bot.run_cycle(None, None)[0]["snapshot"]
    assert first == second
    assert _snapshot_hash(first) == _snapshot_hash(second)


def test_replay_fallback_flags_correctness():
    bot = DeterministicIntelBot(stale=True, missing=True)
    snapshot = bot.run_cycle(None, None)[0]["snapshot"]
    assert snapshot["fallback_flags"] == {"stale": True, "missing": True}


def test_replay_quality_degrades_under_stale_missing_inputs():
    base = ReplayEngine().run(DeterministicIntelBot(stale=False, missing=False), None, None, cycles=3)
    degraded = ReplayEngine().run(DeterministicIntelBot(stale=True, missing=True), None, None, cycles=3)

    assert base.approved == 3
    assert degraded.approved == 0
    assert degraded.block_reasons.get("quality_gate") == 3
