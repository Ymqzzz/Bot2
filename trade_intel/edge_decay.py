from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .config import TradeIntelConfig
from .models import EdgeHealthSnapshot
from .reason_codes import (
    EDGE_DISABLE_THRESHOLD_REACHED,
    EDGE_EXECUTION_LOSS_RISE,
    EDGE_EXPECTANCY_DROP,
    EDGE_FAST_INVALIDATION_RISE,
    EDGE_LOW_SAMPLE,
    EDGE_TIMING_LOSS_RISE,
)


class EdgeDecayEngine:
    def __init__(self, config: TradeIntelConfig):
        self.config = config

    def evaluate_scope(
        self,
        scope_type: str,
        scope_key: str,
        scope_metrics: dict[str, Any],
        disable_until: datetime | None = None,
    ) -> EdgeHealthSnapshot:
        n = int(scope_metrics.get("sample_size", 0))
        reasons: list[str] = []
        if n < self.config.EDGE_MIN_SAMPLE_SIZE:
            reasons.append(EDGE_LOW_SAMPLE)
        expectancy = float(scope_metrics.get("expectancy_r") or 0.0)
        fast_inv = float(scope_metrics.get("fast_invalidation_rate") or 0.0)
        exe_loss = float(scope_metrics.get("execution_loss_rate") or 0.0)
        timing_loss = float(scope_metrics.get("timing_loss_rate") or 0.0)
        drawdown = float(scope_metrics.get("rolling_drawdown_r") or 0.0)

        score = 0.5
        score += max(-0.4, min(0.4, expectancy * 0.8))
        score -= min(0.3, fast_inv * 0.25)
        score -= min(0.3, exe_loss * 0.2)
        score -= min(0.3, timing_loss * 0.2)
        score -= min(0.25, drawdown * 0.08)
        if n < self.config.EDGE_MIN_SAMPLE_SIZE:
            score -= 0.05
        score = max(0.0, min(1.0, score))

        if expectancy < 0:
            reasons.append(EDGE_EXPECTANCY_DROP)
        if fast_inv > 0.3:
            reasons.append(EDGE_FAST_INVALIDATION_RISE)
        if exe_loss > 0.25:
            reasons.append(EDGE_EXECUTION_LOSS_RISE)
        if timing_loss > 0.25:
            reasons.append(EDGE_TIMING_LOSS_RISE)

        now = datetime.now(timezone.utc)
        disabled_now = disable_until is not None and disable_until > now
        disable = disabled_now or (
            n >= self.config.EDGE_MIN_SAMPLE_SIZE
            and expectancy <= self.config.EDGE_DISABLE_EXPECTANCY_THRESHOLD_R
            and (
                fast_inv >= self.config.EDGE_DISABLE_FAST_INVALIDATION_THRESHOLD
                or exe_loss >= self.config.EDGE_DISABLE_EXECUTION_LOSS_THRESHOLD
                or timing_loss >= self.config.EDGE_DISABLE_TIMING_LOSS_THRESHOLD
            )
        )
        if disable:
            reasons.append(EDGE_DISABLE_THRESHOLD_REACHED)

        if disable:
            state = "disabled"
            throttle = 0.0
        elif score < 0.2:
            state = "degraded"
            throttle = max(self.config.EDGE_THROTTLE_MULTIPLIER_FLOOR, 0.55)
        elif score < 0.35:
            state = "weak"
            throttle = 0.7
        elif score < 0.5:
            state = "watch"
            throttle = 0.85
        elif score < 0.75:
            state = "healthy"
            throttle = 1.0
        else:
            state = "strong"
            throttle = 1.1

        return EdgeHealthSnapshot(
            scope_type=scope_type,
            scope_key=scope_key,
            sample_size=n,
            win_rate=scope_metrics.get("win_rate"),
            expectancy_r=scope_metrics.get("expectancy_r"),
            profit_factor=scope_metrics.get("profit_factor"),
            avg_mfe_r=scope_metrics.get("avg_mfe_r"),
            avg_mae_r=scope_metrics.get("avg_mae_r"),
            avg_slippage_bps=scope_metrics.get("avg_slippage_bps"),
            timing_loss_rate=scope_metrics.get("timing_loss_rate"),
            execution_loss_rate=scope_metrics.get("execution_loss_rate"),
            fast_invalidation_rate=scope_metrics.get("fast_invalidation_rate"),
            rolling_drawdown_r=scope_metrics.get("rolling_drawdown_r"),
            edge_score=score,
            edge_state=state,
            throttle_multiplier=throttle,
            disable_recommended=disable,
            reason_codes=reasons,
            asof=now,
        )

    def aggregate_trade_context_edge(self, snapshots: list[EdgeHealthSnapshot]) -> EdgeHealthSnapshot:
        if not snapshots:
            return self.evaluate_scope("aggregate", "none", {"sample_size": 0})
        score = sum(s.edge_score for s in snapshots) / len(snapshots)
        throttle = min(s.throttle_multiplier for s in snapshots)
        disable = any(s.disable_recommended for s in snapshots)
        state = "disabled" if disable else ("weak" if score < 0.4 else "healthy" if score < 0.7 else "strong")
        return EdgeHealthSnapshot(
            scope_type="aggregate",
            scope_key="context",
            sample_size=min(s.sample_size for s in snapshots),
            win_rate=None,
            expectancy_r=None,
            profit_factor=None,
            avg_mfe_r=None,
            avg_mae_r=None,
            avg_slippage_bps=None,
            timing_loss_rate=None,
            execution_loss_rate=None,
            fast_invalidation_rate=None,
            rolling_drawdown_r=None,
            edge_score=score,
            edge_state=state,
            throttle_multiplier=throttle,
            disable_recommended=disable,
            reason_codes=[r for s in snapshots for r in s.reason_codes],
            asof=datetime.now(timezone.utc),
        )

    def get_throttle_multiplier(self, snapshots: list[EdgeHealthSnapshot]) -> float:
        return self.aggregate_trade_context_edge(snapshots).throttle_multiplier

    def should_block_trade(self, snapshots: list[EdgeHealthSnapshot]) -> tuple[bool, list[str]]:
        agg = self.aggregate_trade_context_edge(snapshots)
        return agg.disable_recommended, agg.reason_codes

    def disable_until_timestamp(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(minutes=self.config.EDGE_DISABLE_DURATION_MINUTES)
