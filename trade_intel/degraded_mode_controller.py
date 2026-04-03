from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DegradedModeDecision:
    enabled: bool
    size_cap: float
    disabled_modules: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)


class DegradedModeController:
    def decide(self, stale_seconds: int, nan_ratio: float, drift: float, dependency_failures: list[str]) -> DegradedModeDecision:
        reasons: list[str] = []
        disabled: list[str] = []
        cap = 1.0
        enabled = False

        if stale_seconds > 90:
            enabled = True
            cap = min(cap, 0.65)
            reasons.append("HEALTH_DATA_STALE")
            disabled.append("high_frequency_strategies")
        if nan_ratio > 0.10:
            enabled = True
            cap = min(cap, 0.50)
            reasons.append("HEALTH_FEATURE_INTEGRITY_LOW")
            disabled.append("feature_dependent_engines")
        if drift > 0.5:
            enabled = True
            cap = min(cap, 0.55)
            reasons.append("HEALTH_LIVE_BACKTEST_DRIFT")
            disabled.append("aggressive_sizing")
        if dependency_failures:
            enabled = True
            cap = min(cap, 0.45)
            reasons.append("HEALTH_DEPENDENCY_FAILURE")
            disabled.extend(dependency_failures)

        return DegradedModeDecision(enabled=enabled, size_cap=cap, disabled_modules=sorted(set(disabled)), reason_codes=reasons)
