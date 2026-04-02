from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    nullable: bool = False


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec("ret_1"),
    FeatureSpec("ret_3"),
    FeatureSpec("ret_12"),
    FeatureSpec("realized_vol_20"),
    FeatureSpec("atr_norm"),
    FeatureSpec("trend_slope_20"),
    FeatureSpec("mom_10"),
    FeatureSpec("vwap_distance"),
    FeatureSpec("daily_range_pos"),
    FeatureSpec("prev_day_hilo_proximity"),
    FeatureSpec("liquidity_sweep_flag"),
    FeatureSpec("bos_flag"),
    FeatureSpec("trend_regime_score"),
    FeatureSpec("chop_regime_score"),
    FeatureSpec("spread"),
    FeatureSpec("normalized_spread"),
    FeatureSpec("slippage_estimate"),
    FeatureSpec("tick_imbalance", nullable=True),
    FeatureSpec("orderbook_imbalance", nullable=True),
    FeatureSpec("depth_imbalance", nullable=True),
    FeatureSpec("top_book_stability", nullable=True),
    FeatureSpec("price_impact", nullable=True),
    FeatureSpec("latency_ms"),
    FeatureSpec("volatility_burst_flag"),
    FeatureSpec("fill_quality_estimate", nullable=True),
    FeatureSpec("confluence_score"),
    FeatureSpec("buy_score"),
    FeatureSpec("sell_score"),
    FeatureSpec("neutral_score"),
    FeatureSpec("confidence_score"),
    FeatureSpec("strategy_agreement_count"),
    FeatureSpec("strategy_disagreement_count"),
    FeatureSpec("signal_streak"),
    FeatureSpec("instrument_recent_perf"),
    FeatureSpec("setup_recent_perf"),
    FeatureSpec("open_positions"),
    FeatureSpec("open_risk"),
    FeatureSpec("unrealized_pnl"),
    FeatureSpec("daily_drawdown"),
    FeatureSpec("weekly_drawdown"),
    FeatureSpec("trade_count_today"),
    FeatureSpec("loss_streak"),
    FeatureSpec("risk_budget_remaining"),
    FeatureSpec("correlation_exposure"),
    FeatureSpec("margin_utilization"),
    FeatureSpec("time_since_last_trade"),
    FeatureSpec("session_id"),
    FeatureSpec("weekday"),
    FeatureSpec("hour_bucket"),
    FeatureSpec("macro_event_proximity"),
    FeatureSpec("news_blackout_flag"),
    FeatureSpec("weekend_liquidity_flag"),
    FeatureSpec("regime_cluster_id"),
)


def feature_names() -> list[str]:
    return [f.name for f in FEATURE_SPECS]


def schema_hash(specs: Iterable[FeatureSpec] = FEATURE_SPECS) -> str:
    payload = "|".join(f"{s.name}:{int(s.nullable)}" for s in specs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
