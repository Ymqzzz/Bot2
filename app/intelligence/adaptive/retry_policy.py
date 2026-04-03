from __future__ import annotations

from app.intelligence.base import clamp


class RetryPolicy:
    def decide(
        self,
        *,
        thesis_survives: bool,
        regime_improved: bool,
        retest_quality: float,
        fatigue: float,
        failure_type: str,
    ) -> tuple[bool, float, float, list[str]]:
        reasons: list[str] = []
        if not thesis_survives:
            reasons.append("RETRY_THESIS_INVALID")
            return False, 0.0, 1.0, reasons
        if not regime_improved:
            reasons.append("RETRY_REGIME_DETERIORATED")
            return False, 0.0, 1.0, reasons

        threshold = clamp(0.45 + fatigue * 0.35)
        if retest_quality < threshold:
            reasons.append("RETRY_QUALITY_INSUFFICIENT")
            return False, 0.0, threshold, reasons

        base_size = 1.0 - fatigue * 0.5
        if failure_type == "execution_failure":
            base_size *= 0.9
        if failure_type == "noisy_invalidation":
            base_size *= 0.8
        reasons.append("RETRY_ALLOWED")
        return True, clamp(base_size, 0.2, 1.0), threshold, reasons
