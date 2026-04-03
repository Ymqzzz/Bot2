from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float, low: float | None = None, high: float | None = None) -> float:
    val = float(os.environ.get(name, str(default)))
    if low is not None and val < low:
        raise ValueError(f"{name} must be >= {low}")
    if high is not None and val > high:
        raise ValueError(f"{name} must be <= {high}")
    return val


def _get_int(name: str, default: int, low: int | None = None) -> int:
    val = int(os.environ.get(name, str(default)))
    if low is not None and val < low:
        raise ValueError(f"{name} must be >= {low}")
    return val


@dataclass(frozen=True)
class TradeIntelConfig:
    TRADE_INTEL_ENABLED: bool = _get_bool("TRADE_INTEL_ENABLED", True)
    TRADE_INTEL_STRICT_MODE: bool = _get_bool("TRADE_INTEL_STRICT_MODE", True)
    TRADE_INTEL_STORAGE_ENABLED: bool = _get_bool("TRADE_INTEL_STORAGE_ENABLED", True)
    TRADE_INTEL_JSONL_PATH: str = os.environ.get("TRADE_INTEL_JSONL_PATH", "trade_intel_records.jsonl")
    TRADE_INTEL_SQLITE_ENABLED: bool = _get_bool("TRADE_INTEL_SQLITE_ENABLED", False)

    ATTRIBUTION_ENABLED: bool = _get_bool("ATTRIBUTION_ENABLED", True)
    MIN_BARS_FOR_POST_TRADE_CLASSIFICATION: int = _get_int("MIN_BARS_FOR_POST_TRADE_CLASSIFICATION", 3, 1)
    FAST_INVALIDATION_SECONDS: int = _get_int("FAST_INVALIDATION_SECONDS", 900, 1)
    ADVERSE_SELECTION_LOOKAHEAD_SECONDS: int = _get_int("ADVERSE_SELECTION_LOOKAHEAD_SECONDS", 120, 1)
    MFE_GIVEBACK_HIGH_THRESHOLD: float = _get_float("MFE_GIVEBACK_HIGH_THRESHOLD", 0.55, 0.0, 1.0)
    TIMING_LOSS_MAE_THRESHOLD_R: float = _get_float("TIMING_LOSS_MAE_THRESHOLD_R", 0.6, 0.0)
    EXECUTION_LOSS_SLIPPAGE_THRESHOLD_BPS: float = _get_float("EXECUTION_LOSS_SLIPPAGE_THRESHOLD_BPS", 2.0, 0.0)

    ADAPTIVE_SIZING_ENABLED: bool = _get_bool("ADAPTIVE_SIZING_ENABLED", True)
    BASE_RISK_FRACTION_DEFAULT: float = _get_float("BASE_RISK_FRACTION_DEFAULT", 0.005, 0.0)
    SIZE_MULTIPLIER_MIN: float = _get_float("SIZE_MULTIPLIER_MIN", 0.50, 0.01)
    SIZE_MULTIPLIER_MAX: float = _get_float("SIZE_MULTIPLIER_MAX", 1.40, 0.01)
    INTEL_QUALITY_SIZE_WEIGHT: float = _get_float("INTEL_QUALITY_SIZE_WEIGHT", 0.40, 0.0)
    EXECUTION_QUALITY_SIZE_WEIGHT: float = _get_float("EXECUTION_QUALITY_SIZE_WEIGHT", 0.25, 0.0)
    REGIME_ALIGNMENT_SIZE_WEIGHT: float = _get_float("REGIME_ALIGNMENT_SIZE_WEIGHT", 0.20, 0.0)
    EDGE_HEALTH_SIZE_WEIGHT: float = _get_float("EDGE_HEALTH_SIZE_WEIGHT", 0.35, 0.0)
    SESSION_EDGE_SIZE_WEIGHT: float = _get_float("SESSION_EDGE_SIZE_WEIGHT", 0.15, 0.0)
    RECENT_PERFORMANCE_SIZE_WEIGHT: float = _get_float("RECENT_PERFORMANCE_SIZE_WEIGHT", 0.15, 0.0)
    EVENT_RISK_SIZE_PENALTY: float = _get_float("EVENT_RISK_SIZE_PENALTY", 0.70, 0.0, 1.0)
    EXPENSIVE_SPREAD_SIZE_PENALTY: float = _get_float("EXPENSIVE_SPREAD_SIZE_PENALTY", 0.75, 0.0, 1.0)
    LOW_INTEL_BLOCK_THRESHOLD: float = _get_float("LOW_INTEL_BLOCK_THRESHOLD", 0.20, 0.0, 1.0)
    LOW_EDGE_BLOCK_THRESHOLD: float = _get_float("LOW_EDGE_BLOCK_THRESHOLD", 0.25, 0.0, 1.0)

    SMART_EXITS_ENABLED: bool = _get_bool("SMART_EXITS_ENABLED", True)
    ENABLE_PARTIALS: bool = _get_bool("ENABLE_PARTIALS", True)
    ENABLE_PROFILE_BASED_PARTIALS: bool = _get_bool("ENABLE_PROFILE_BASED_PARTIALS", True)
    ENABLE_STRUCTURE_BASED_PARTIALS: bool = _get_bool("ENABLE_STRUCTURE_BASED_PARTIALS", True)
    ENABLE_TIME_STOPS: bool = _get_bool("ENABLE_TIME_STOPS", True)
    ENABLE_BREAK_EVEN_ARMING: bool = _get_bool("ENABLE_BREAK_EVEN_ARMING", True)
    ENABLE_REGIME_INVALIDATION_EXITS: bool = _get_bool("ENABLE_REGIME_INVALIDATION_EXITS", True)
    ENABLE_EXECUTION_DISLOCATION_EXITS: bool = _get_bool("ENABLE_EXECUTION_DISLOCATION_EXITS", True)
    MAX_MFE_GIVEBACK_FRACTION: float = _get_float("MAX_MFE_GIVEBACK_FRACTION", 0.55, 0.0, 1.0)
    TRAILING_ARM_R_MULTIPLE: float = _get_float("TRAILING_ARM_R_MULTIPLE", 1.4, 0.0)
    BREAK_EVEN_ARM_R_MULTIPLE: float = _get_float("BREAK_EVEN_ARM_R_MULTIPLE", 1.0, 0.0)
    DEFAULT_MAX_HOLD_SECONDS: int = _get_int("DEFAULT_MAX_HOLD_SECONDS", 3600, 1)
    TREND_PULLBACK_MAX_HOLD_SECONDS: int = _get_int("TREND_PULLBACK_MAX_HOLD_SECONDS", 5400, 1)
    SWEEP_REVERSAL_MAX_HOLD_SECONDS: int = _get_int("SWEEP_REVERSAL_MAX_HOLD_SECONDS", 2400, 1)
    BREAKOUT_MAX_HOLD_SECONDS: int = _get_int("BREAKOUT_MAX_HOLD_SECONDS", 1800, 1)
    MEAN_REVERSION_MAX_HOLD_SECONDS: int = _get_int("MEAN_REVERSION_MAX_HOLD_SECONDS", 3000, 1)

    EDGE_DECAY_ENABLED: bool = _get_bool("EDGE_DECAY_ENABLED", True)
    EDGE_ROLLING_WINDOW_TRADES: int = _get_int("EDGE_ROLLING_WINDOW_TRADES", 100, 5)
    EDGE_MIN_SAMPLE_SIZE: int = _get_int("EDGE_MIN_SAMPLE_SIZE", 20, 5)
    EDGE_DISABLE_EXPECTANCY_THRESHOLD_R: float = _get_float("EDGE_DISABLE_EXPECTANCY_THRESHOLD_R", -0.25)
    EDGE_DISABLE_FAST_INVALIDATION_THRESHOLD: float = _get_float("EDGE_DISABLE_FAST_INVALIDATION_THRESHOLD", 0.45, 0.0, 1.0)
    EDGE_DISABLE_EXECUTION_LOSS_THRESHOLD: float = _get_float("EDGE_DISABLE_EXECUTION_LOSS_THRESHOLD", 0.35, 0.0, 1.0)
    EDGE_DISABLE_TIMING_LOSS_THRESHOLD: float = _get_float("EDGE_DISABLE_TIMING_LOSS_THRESHOLD", 0.40, 0.0, 1.0)
    EDGE_THROTTLE_MULTIPLIER_FLOOR: float = _get_float("EDGE_THROTTLE_MULTIPLIER_FLOOR", 0.5, 0.0, 1.0)
    EDGE_DISABLE_DURATION_MINUTES: int = _get_int("EDGE_DISABLE_DURATION_MINUTES", 240, 1)
    EDGE_SCOPE_STRATEGY_ENABLED: bool = _get_bool("EDGE_SCOPE_STRATEGY_ENABLED", True)
    EDGE_SCOPE_INSTRUMENT_ENABLED: bool = _get_bool("EDGE_SCOPE_INSTRUMENT_ENABLED", True)
    EDGE_SCOPE_SESSION_ENABLED: bool = _get_bool("EDGE_SCOPE_SESSION_ENABLED", True)
    EDGE_SCOPE_SETUP_ENABLED: bool = _get_bool("EDGE_SCOPE_SETUP_ENABLED", True)

    PERF_TRACK_BY_STRATEGY: bool = _get_bool("PERF_TRACK_BY_STRATEGY", True)
    PERF_TRACK_BY_INSTRUMENT: bool = _get_bool("PERF_TRACK_BY_INSTRUMENT", True)
    PERF_TRACK_BY_SESSION: bool = _get_bool("PERF_TRACK_BY_SESSION", True)
    PERF_TRACK_BY_REGIME: bool = _get_bool("PERF_TRACK_BY_REGIME", True)
    PERF_TRACK_BY_SETUP_TYPE: bool = _get_bool("PERF_TRACK_BY_SETUP_TYPE", True)
    PERF_TRACK_BY_SPREAD_REGIME: bool = _get_bool("PERF_TRACK_BY_SPREAD_REGIME", True)

    DECISION_ENGINE_ENABLED: bool = _get_bool("DECISION_ENGINE_ENABLED", True)
    DECISION_MIN_EXECUTION_QUALITY: float = _get_float("DECISION_MIN_EXECUTION_QUALITY", 0.25, 0.0, 1.0)
    DECISION_MAX_DOWNSIDE_R: float = _get_float("DECISION_MAX_DOWNSIDE_R", 0.85, 0.0)
    DECISION_MAX_TRANSITION_RISK: float = _get_float("DECISION_MAX_TRANSITION_RISK", 0.70, 0.0, 1.0)


def load_config() -> TradeIntelConfig:
    return TradeIntelConfig()
