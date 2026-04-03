from __future__ import annotations


class FailureCauseClassifier:
    def classify(self, *, stop_reason: str, slippage: float, invalidation_clean: bool) -> str:
        if slippage > 0.7:
            return "execution_failure"
        if stop_reason in {"hard_invalidation", "regime_flip"} and invalidation_clean:
            return "thesis_failure"
        if stop_reason in {"noise_stop", "wick_sweep"} and not invalidation_clean:
            return "noisy_invalidation"
        return "mixed_failure"
