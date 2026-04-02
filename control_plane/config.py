from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os


class RegimeUncertainBehavior(str, Enum):
    DEGRADE = "degrade"
    RESTRICT = "restrict"
    BLOCK = "block"


def _b(name: str, default: bool) -> bool:
    return str(os.environ.get(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class ControlPlaneConfig:
    CONTROL_PLANE_ENABLED: bool = field(default_factory=lambda: _b("CONTROL_PLANE_ENABLED", True))
    CONTROL_PLANE_STRICT_MODE: bool = field(default_factory=lambda: _b("CONTROL_PLANE_STRICT_MODE", False))
    REGIME_ENGINE_ENABLED: bool = field(default_factory=lambda: _b("REGIME_ENGINE_ENABLED", True))
    REGIME_LOOKBACK_BARS_M5: int = field(default_factory=lambda: _i("REGIME_LOOKBACK_BARS_M5", 120))
    REGIME_LOOKBACK_BARS_M15: int = field(default_factory=lambda: _i("REGIME_LOOKBACK_BARS_M15", 96))
    REGIME_LOOKBACK_BARS_H1: int = field(default_factory=lambda: _i("REGIME_LOOKBACK_BARS_H1", 96))
    REGIME_MIN_CONFIDENCE: float = field(default_factory=lambda: _f("REGIME_MIN_CONFIDENCE", 0.55))
    REGIME_UNCERTAIN_BEHAVIOR: RegimeUncertainBehavior = field(
        default_factory=lambda: RegimeUncertainBehavior(os.environ.get("REGIME_UNCERTAIN_BEHAVIOR", "restrict").strip().lower())
    )
    TREND_STRENGTH_THRESHOLD: float = field(default_factory=lambda: _f("TREND_STRENGTH_THRESHOLD", 0.62))
    ROTATION_THRESHOLD: float = field(default_factory=lambda: _f("ROTATION_THRESHOLD", 0.58))
    COMPRESSION_THRESHOLD: float = field(default_factory=lambda: _f("COMPRESSION_THRESHOLD", 0.60))
    EXPANSION_THRESHOLD: float = field(default_factory=lambda: _f("EXPANSION_THRESHOLD", 0.60))
    DEAD_ZONE_THRESHOLD: float = field(default_factory=lambda: _f("DEAD_ZONE_THRESHOLD", 0.65))
    EVENT_CHAOS_THRESHOLD: float = field(default_factory=lambda: _f("EVENT_CHAOS_THRESHOLD", 0.70))
    PORTFOLIO_ALLOCATOR_ENABLED: bool = field(default_factory=lambda: _b("PORTFOLIO_ALLOCATOR_ENABLED", True))
    ALLOC_MAX_NEW_TRADES_PER_CYCLE: int = field(default_factory=lambda: _i("ALLOC_MAX_NEW_TRADES_PER_CYCLE", 3))
    ALLOC_MAX_USD_NET_EXPOSURE: float = field(default_factory=lambda: _f("ALLOC_MAX_USD_NET_EXPOSURE", 0.04))
    ALLOC_MAX_SINGLE_MACRO_CLUSTER_RISK: float = field(default_factory=lambda: _f("ALLOC_MAX_SINGLE_MACRO_CLUSTER_RISK", 0.02))
    ALLOC_MAX_CORRELATED_BUCKET_RISK: float = field(default_factory=lambda: _f("ALLOC_MAX_CORRELATED_BUCKET_RISK", 0.02))
    ALLOC_MAX_INSTRUMENT_DUPLICATION: int = field(default_factory=lambda: _i("ALLOC_MAX_INSTRUMENT_DUPLICATION", 1))
    ALLOC_MIN_PRIORITY_SCORE: float = field(default_factory=lambda: _f("ALLOC_MIN_PRIORITY_SCORE", 0.20))
    ALLOC_ENABLE_RESIZING: bool = field(default_factory=lambda: _b("ALLOC_ENABLE_RESIZING", True))
    ALLOC_ENABLE_BLOCKING: bool = field(default_factory=lambda: _b("ALLOC_ENABLE_BLOCKING", True))
    ALLOC_PRIORITY_EV_WEIGHT: float = field(default_factory=lambda: _f("ALLOC_PRIORITY_EV_WEIGHT", 0.35))
    ALLOC_PRIORITY_EXEC_WEIGHT: float = field(default_factory=lambda: _f("ALLOC_PRIORITY_EXEC_WEIGHT", 0.20))
    ALLOC_PRIORITY_EDGE_WEIGHT: float = field(default_factory=lambda: _f("ALLOC_PRIORITY_EDGE_WEIGHT", 0.15))
    ALLOC_PRIORITY_REGIME_WEIGHT: float = field(default_factory=lambda: _f("ALLOC_PRIORITY_REGIME_WEIGHT", 0.15))
    ALLOC_PRIORITY_EVENT_WEIGHT: float = field(default_factory=lambda: _f("ALLOC_PRIORITY_EVENT_WEIGHT", 0.10))
    CORRELATION_LOOKBACK_DAYS: int = field(default_factory=lambda: _i("CORRELATION_LOOKBACK_DAYS", 30))
    CORRELATION_MIN_ABS_FOR_CLUSTER: float = field(default_factory=lambda: _f("CORRELATION_MIN_ABS_FOR_CLUSTER", 0.65))
    CORRELATION_REFRESH_MINUTES: int = field(default_factory=lambda: _i("CORRELATION_REFRESH_MINUTES", 60))
    EVENT_ENGINE_ENABLED: bool = field(default_factory=lambda: _b("EVENT_ENGINE_ENABLED", True))
    EVENT_CALENDAR_ENABLED: bool = field(default_factory=lambda: _b("EVENT_CALENDAR_ENABLED", True))
    EVENT_PRE_LOCKOUT_MINUTES: int = field(default_factory=lambda: _i("EVENT_PRE_LOCKOUT_MINUTES", 30))
    EVENT_POST_DIGESTION_MINUTES: int = field(default_factory=lambda: _i("EVENT_POST_DIGESTION_MINUTES", 45))
    EVENT_SPREAD_NORMALIZATION_WINDOW_MINUTES: int = field(default_factory=lambda: _i("EVENT_SPREAD_NORMALIZATION_WINDOW_MINUTES", 20))
    EVENT_ALLOW_BREAKOUT_POST_RELEASE_ONLY: bool = field(default_factory=lambda: _b("EVENT_ALLOW_BREAKOUT_POST_RELEASE_ONLY", True))
    EVENT_BLOCK_MEAN_REVERSION_NEAR_HIGH_IMPACT: bool = field(default_factory=lambda: _b("EVENT_BLOCK_MEAN_REVERSION_NEAR_HIGH_IMPACT", True))
    EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE: bool = field(default_factory=lambda: _b("EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE", False))
    CONFLUENCE_ENGINE_ENABLED: bool = field(default_factory=lambda: _b("CONFLUENCE_ENGINE_ENABLED", True))
    CONFLUENCE_MIN_SCORE_TO_ALLOCATE: float = field(default_factory=lambda: _f("CONFLUENCE_MIN_SCORE_TO_ALLOCATE", 0.25))
    CONFLUENCE_WEIGHT_EV: float = field(default_factory=lambda: _f("CONFLUENCE_WEIGHT_EV", 0.25))
    CONFLUENCE_WEIGHT_CONFIDENCE: float = field(default_factory=lambda: _f("CONFLUENCE_WEIGHT_CONFIDENCE", 0.20))
    CONFLUENCE_WEIGHT_EDGE: float = field(default_factory=lambda: _f("CONFLUENCE_WEIGHT_EDGE", 0.15))
    CONFLUENCE_WEIGHT_REGIME: float = field(default_factory=lambda: _f("CONFLUENCE_WEIGHT_REGIME", 0.15))
    CONFLUENCE_WEIGHT_EVENT: float = field(default_factory=lambda: _f("CONFLUENCE_WEIGHT_EVENT", 0.10))
    CONFLUENCE_WEIGHT_EXECUTION: float = field(default_factory=lambda: _f("CONFLUENCE_WEIGHT_EXECUTION", 0.15))
    CONFLUENCE_CORRELATION_PENALTY_WEIGHT: float = field(default_factory=lambda: _f("CONFLUENCE_CORRELATION_PENALTY_WEIGHT", 0.40))
    CONFLUENCE_RISK_MULTIPLIER_BOUNDS: tuple[float, float] = field(
        default_factory=lambda: (
            _f("CONFLUENCE_RISK_MULTIPLIER_MIN", 0.5),
            _f("CONFLUENCE_RISK_MULTIPLIER_MAX", 1.2),
        )
    )
    SURVEILLANCE_ENGINE_ENABLED: bool = field(default_factory=lambda: _b("SURVEILLANCE_ENGINE_ENABLED", True))
    SURVEILLANCE_MAX_TOXICITY: float = field(default_factory=lambda: _f("SURVEILLANCE_MAX_TOXICITY", 0.85))
    SURVEILLANCE_SOFT_TOXICITY: float = field(default_factory=lambda: _f("SURVEILLANCE_SOFT_TOXICITY", 0.65))
    EXECUTION_INTEL_ENABLED: bool = field(default_factory=lambda: _b("EXECUTION_INTEL_ENABLED", True))
    EXECUTION_FILL_PROB_THRESHOLD: float = field(default_factory=lambda: _f("EXECUTION_FILL_PROB_THRESHOLD", 0.35))
    EXECUTION_MAX_EXPECTED_SLIPPAGE_BPS: float = field(default_factory=lambda: _f("EXECUTION_MAX_EXPECTED_SLIPPAGE_BPS", 3.0))
    EXECUTION_MAX_LATE_ENTRY_RISK: float = field(default_factory=lambda: _f("EXECUTION_MAX_LATE_ENTRY_RISK", 0.75))
    EXECUTION_MAX_ESCAPE_RISK: float = field(default_factory=lambda: _f("EXECUTION_MAX_ESCAPE_RISK", 0.85))
    EXECUTION_REPRICE_ENABLED: bool = field(default_factory=lambda: _b("EXECUTION_REPRICE_ENABLED", True))
    EXECUTION_DEFAULT_MAX_RETRIES: int = field(default_factory=lambda: _i("EXECUTION_DEFAULT_MAX_RETRIES", 2))
    EXECUTION_DEFAULT_CANCEL_AFTER_SECONDS: int = field(default_factory=lambda: _i("EXECUTION_DEFAULT_CANCEL_AFTER_SECONDS", 90))
    ORDER_TACTICS_ENABLED: bool = field(default_factory=lambda: _b("ORDER_TACTICS_ENABLED", True))
    TACTIC_USE_PASSIVE_LIMIT_FOR_ROTATION: bool = field(default_factory=lambda: _b("TACTIC_USE_PASSIVE_LIMIT_FOR_ROTATION", True))
    TACTIC_USE_AGGRESSIVE_STOP_FOR_EXPANSION: bool = field(default_factory=lambda: _b("TACTIC_USE_AGGRESSIVE_STOP_FOR_EXPANSION", True))
    TACTIC_ALLOW_STAGING: bool = field(default_factory=lambda: _b("TACTIC_ALLOW_STAGING", True))
    TACTIC_MAX_CLIPS: int = field(default_factory=lambda: _i("TACTIC_MAX_CLIPS", 3))
    TACTIC_MIN_CLIP_SECONDS: int = field(default_factory=lambda: _i("TACTIC_MIN_CLIP_SECONDS", 4))
    TACTIC_FALLBACK_TO_MARKET_ALLOWED: bool = field(default_factory=lambda: _b("TACTIC_FALLBACK_TO_MARKET_ALLOWED", True))

    def validate(self) -> None:
        if not (0.0 <= self.REGIME_MIN_CONFIDENCE <= 1.0):
            raise ValueError("REGIME_MIN_CONFIDENCE must be [0,1]")
        if self.ALLOC_MAX_NEW_TRADES_PER_CYCLE < 1:
            raise ValueError("ALLOC_MAX_NEW_TRADES_PER_CYCLE must be >=1")
        if self.TACTIC_MAX_CLIPS < 1:
            raise ValueError("TACTIC_MAX_CLIPS must be >=1")
        lo, hi = self.CONFLUENCE_RISK_MULTIPLIER_BOUNDS
        if not (0.0 <= self.CONFLUENCE_MIN_SCORE_TO_ALLOCATE <= 1.0):
            raise ValueError("CONFLUENCE_MIN_SCORE_TO_ALLOCATE must be [0,1]")
        if lo <= 0 or hi <= 0 or lo > hi:
            raise ValueError("CONFLUENCE risk multiplier bounds must be positive and ordered")
        if not (0.0 <= self.SURVEILLANCE_SOFT_TOXICITY <= 1.0 and 0.0 <= self.SURVEILLANCE_MAX_TOXICITY <= 1.0):
            raise ValueError("Surveillance thresholds must be [0,1]")
        if self.SURVEILLANCE_SOFT_TOXICITY > self.SURVEILLANCE_MAX_TOXICITY:
            raise ValueError("SURVEILLANCE_SOFT_TOXICITY must be <= SURVEILLANCE_MAX_TOXICITY")


def load_config() -> ControlPlaneConfig:
    cfg = ControlPlaneConfig()
    cfg.validate()
    return cfg
