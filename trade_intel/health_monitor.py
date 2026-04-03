from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .circuit_breaker import should_trip
from .clock_sync_guard import clock_skew_ms
from .data_freshness_monitor import data_age_seconds
from .degraded_mode_controller import DegradedModeController
from .feature_integrity_checker import FeatureIntegrityChecker
from .live_vs_backtest_drift_detector import drift_score


@dataclass(slots=True)
class HealthState:
    status: str
    degraded: bool
    block_trading: bool
    risk_multiplier_cap: float
    reason_codes: list[str] = field(default_factory=list)


class HealthMonitor:
    def __init__(self):
        self.feature_checker = FeatureIntegrityChecker()
        self.degraded_controller = DegradedModeController()

    def assess(self, market_context: dict[str, Any], runtime_context: dict[str, Any]) -> HealthState:
        reasons: list[str] = []
        stale_seconds = data_age_seconds(int(runtime_context.get("now_ts", 0)), int(runtime_context.get("data_ts", runtime_context.get("now_ts", 0)))) if "now_ts" in runtime_context else int(runtime_context.get("data_age_seconds", 0))
        nan_ratio = float(runtime_context.get("nan_feature_ratio", 0.0))
        skew_ms = clock_skew_ms(int(runtime_context.get("provider_ts_ms", 0)), int(runtime_context.get("local_ts_ms", runtime_context.get("provider_ts_ms", 0)))) if "provider_ts_ms" in runtime_context else int(runtime_context.get("clock_skew_ms", 0))
        provider_lag = int(market_context.get("provider_lag_ms", 0))
        drift = drift_score(runtime_context.get("live_metrics", {}), runtime_context.get("expected_metrics", {}))
        integrity = None
        if runtime_context.get("feature_values"):
            integrity = self.feature_checker.assess(
                runtime_context.get("feature_values", {}),
                runtime_context.get("feature_domains", {}),
            )
            nan_ratio = max(nan_ratio, integrity.nan_ratio)

        block = False
        degraded = False
        cap = 1.0

        if stale_seconds > 90:
            reasons.append("HEALTH_DATA_STALE")
            degraded = True
            cap = min(cap, 0.65)
        if nan_ratio > 0.10:
            reasons.append("HEALTH_FEATURE_INTEGRITY_LOW")
            degraded = True
            cap = min(cap, 0.50)
        if skew_ms > 3000:
            reasons.append("HEALTH_CLOCK_SKEW")
            degraded = True
            cap = min(cap, 0.5)
        if provider_lag > 2500:
            reasons.append("HEALTH_PROVIDER_LAG")
            degraded = True
            cap = min(cap, 0.6)
        if drift > 0.5:
            reasons.append("HEALTH_LIVE_BACKTEST_DRIFT")
            degraded = True
            cap = min(cap, 0.55)

        hard_errors = int(runtime_context.get("hard_error_count", 0))
        if should_trip(stale_seconds, nan_ratio, drift, hard_errors):
            block = True
            reasons.append("HEALTH_CIRCUIT_BREAKER")

        degrade = self.degraded_controller.decide(
            stale_seconds=stale_seconds,
            nan_ratio=nan_ratio,
            drift=drift,
            dependency_failures=list(runtime_context.get("dependency_failures", [])),
        )
        if degrade.enabled:
            degraded = True
            cap = min(cap, degrade.size_cap)
            reasons.extend(degrade.reason_codes)

        status = "blocked" if block else "degraded" if degraded else "healthy"
        return HealthState(status=status, degraded=degraded, block_trading=block, risk_multiplier_cap=cap, reason_codes=reasons)
