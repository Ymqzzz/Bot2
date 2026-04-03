from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.adaptive.adaptive_types import RetryDecision
from app.intelligence.adaptive.failure_cause_classifier import FailureCauseClassifier
from app.intelligence.adaptive.retest_quality_model import RetestQualityModel
from app.intelligence.adaptive.retry_fatigue_controller import RetryFatigueController
from app.intelligence.adaptive.retry_policy import RetryPolicy


@dataclass
class ReEntryEngine:
    failure_classifier: FailureCauseClassifier = FailureCauseClassifier()
    retest_quality_model: RetestQualityModel = RetestQualityModel()
    fatigue_controller: RetryFatigueController = RetryFatigueController()
    policy: RetryPolicy = RetryPolicy()

    def evaluate(self, *, context: dict) -> RetryDecision:
        failure_type = self.failure_classifier.classify(
            stop_reason=str(context.get("last_stop_reason", "unknown")),
            slippage=float(context.get("last_slippage_score", 0.0)),
            invalidation_clean=bool(context.get("last_invalidation_clean", False)),
        )
        retest_quality = self.retest_quality_model.score(
            setup_quality_now=float(context.get("setup_quality_now", 0.5)),
            setup_quality_prev=float(context.get("setup_quality_prev", 0.5)),
            regime_improvement=float(context.get("regime_improvement", 0.0)),
        )
        fatigue = self.fatigue_controller.fatigue(int(context.get("retry_count", 0)))
        allow, size_mult, threshold, reasons = self.policy.decide(
            thesis_survives=bool(context.get("thesis_survives", True)),
            regime_improved=bool(context.get("regime_improved", True)),
            retest_quality=retest_quality,
            fatigue=fatigue,
            failure_type=failure_type,
        )
        return RetryDecision(
            allow_retry=allow,
            retry_size_multiplier=size_mult,
            fatigue_score=fatigue,
            threshold_increase=threshold,
            reason_codes=reasons + [f"FAILURE_TYPE_{failure_type.upper()}"] ,
        )
