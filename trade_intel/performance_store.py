from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import TradeIntelConfig
from .edge_decay import EdgeDecayEngine
from .models import EdgeHealthSnapshot, TradeLifecycleRecord


@dataclass
class ScopeStats:
    records: deque[TradeLifecycleRecord]
    disable_until: datetime | None = None


class PerformanceStore:
    def __init__(self, config: TradeIntelConfig, edge_engine: EdgeDecayEngine):
        self.config = config
        self.edge_engine = edge_engine
        self._scopes: dict[tuple[str, str], ScopeStats] = defaultdict(
            lambda: ScopeStats(records=deque(maxlen=self.config.EDGE_ROLLING_WINDOW_TRADES))
        )

    def _scope_keys(self, rec: TradeLifecycleRecord) -> list[tuple[str, str]]:
        fp = rec.fingerprint
        keys: list[tuple[str, str]] = [("strategy", fp.strategy_name)]
        keys.append(("instrument", fp.instrument))
        keys.append(("session", f"{fp.strategy_name}|{fp.session_name}"))
        keys.append(("strategy_instrument", f"{fp.strategy_name}|{fp.instrument}"))
        keys.append(("setup", f"{fp.strategy_name}|{fp.setup_type}"))
        keys.append(("spread", fp.spread_regime))
        return keys

    def update_with_closed_trade(self, record: TradeLifecycleRecord) -> None:
        for key in self._scope_keys(record):
            self._scopes[key].records.append(record)

    def _metrics(self, rows: list[TradeLifecycleRecord]) -> dict[str, Any]:
        n = len(rows)
        if not n:
            return {"sample_size": 0}
        realized = [float(r.realized_r or 0.0) for r in rows]
        wins = [x for x in realized if x > 0]
        losses = [-x for x in realized if x < 0]
        attrs = [r.attribution for r in rows if r.attribution]
        paths = [r.path_metrics for r in rows if r.path_metrics]
        entries = [r.entry_quality for r in rows if r.entry_quality]
        exits = [r.exit_quality for r in rows if r.exit_quality]
        expectancy = sum(realized) / n
        draw = 0.0
        eq = 0.0
        peak = 0.0
        for r in realized:
            eq += r
            peak = max(peak, eq)
            draw = min(draw, eq - peak)
        return {
            "sample_size": n,
            "win_rate": len(wins) / n,
            "expectancy_r": expectancy,
            "profit_factor": (sum(wins) / max(sum(losses), 1e-9)) if losses else None,
            "avg_mfe_r": sum((p.mfe_r for p in paths), 0.0) / max(len(paths), 1),
            "avg_mae_r": sum((p.mae_r for p in paths), 0.0) / max(len(paths), 1),
            "avg_slippage_bps": sum((e.slippage_bps or 0.0 for e in entries), 0.0) / max(len(entries), 1),
            "timing_loss_rate": sum(1 for a in attrs if a.was_timing_loss) / max(len(attrs), 1),
            "execution_loss_rate": sum(1 for a in attrs if a.was_execution_loss) / max(len(attrs), 1),
            "fast_invalidation_rate": sum(1 for a in attrs if a.was_thesis_invalidated_fast) / max(len(attrs), 1),
            "rolling_drawdown_r": abs(draw),
            "avg_entry_quality_score": sum(e.entry_quality_score for e in entries) / max(len(entries), 1),
            "avg_exit_quality_score": sum(e.exit_quality_score for e in exits) / max(len(exits), 1),
        }

    def get_edge_snapshot(self, scope_type: str, scope_key: str) -> EdgeHealthSnapshot:
        stats = self._scopes[(scope_type, scope_key)]
        metrics = self._metrics(list(stats.records))
        return self.edge_engine.evaluate_scope(scope_type, scope_key, metrics, stats.disable_until)

    def get_relevant_edge_snapshots(self, trade_context: dict[str, Any]) -> list[EdgeHealthSnapshot]:
        strategy = trade_context.get("strategy_name", "")
        instrument = trade_context.get("instrument", "")
        session = trade_context.get("session_name", "")
        setup = trade_context.get("setup_type", "")
        keys = [
            ("strategy", strategy),
            ("instrument", instrument),
            ("session", f"{strategy}|{session}"),
            ("strategy_instrument", f"{strategy}|{instrument}"),
            ("setup", f"{strategy}|{setup}"),
        ]
        return [self.get_edge_snapshot(t, k) for t, k in keys]
