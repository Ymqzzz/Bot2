from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(slots=True)
class FeatureIntegrityResult:
    nan_ratio: float
    out_of_domain_ratio: float
    healthy: bool


class FeatureIntegrityChecker:
    def assess(self, features: dict[str, float], domains: dict[str, tuple[float, float]]) -> FeatureIntegrityResult:
        if not features:
            return FeatureIntegrityResult(1.0, 1.0, False)
        nan_count = 0
        ood_count = 0
        for name, value in features.items():
            if not isfinite(value):
                nan_count += 1
                continue
            if name in domains:
                lo, hi = domains[name]
                if value < lo or value > hi:
                    ood_count += 1
        n = len(features)
        nan_ratio = nan_count / n
        ood_ratio = ood_count / n
        return FeatureIntegrityResult(nan_ratio, ood_ratio, nan_ratio < 0.1 and ood_ratio < 0.2)
