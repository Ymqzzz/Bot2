from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from app.intelligence.institutional.schemas import (
    FeatureGovernanceReport,
    FeatureHealth,
    FeatureReference,
)


@dataclass
class FeatureRunningStats:
    count: int = 0
    mean_value: float = 0.0
    m2: float = 0.0

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean_value
        self.mean_value += delta / self.count
        delta2 = value - self.mean_value
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def std(self) -> float:
        v = self.variance
        if v <= 0:
            return 1e-6
        return v ** 0.5


class DistributionShiftDetector:
    def score(self, value: float | None, ref: FeatureReference) -> float:
        if value is None:
            return 1.0
        z = abs((value - ref.mean) / max(ref.std, 1e-6))
        band_penalty = 0.0
        if value < ref.lower:
            band_penalty = min(1.0, (ref.lower - value) / max(abs(ref.lower), 1e-6))
        elif value > ref.upper:
            band_penalty = min(1.0, (value - ref.upper) / max(abs(ref.upper), 1e-6))
        return max(0.0, min(1.0, z / 5.0 + band_penalty * 0.5))


class FeatureDriftMonitor:
    def __init__(self) -> None:
        self._stats: dict[str, FeatureRunningStats] = defaultdict(FeatureRunningStats)
        self._detector = DistributionShiftDetector()

    def update(self, features: dict[str, float]) -> None:
        for k, v in features.items():
            self._stats[k].update(v)

    def drift(self, feature: str, value: float | None, ref: FeatureReference) -> float:
        stream = self._stats[feature]
        stream_std = stream.std
        stream_shift = 0.0 if stream.count < 10 or value is None else abs((value - stream.mean_value) / stream_std)
        ref_shift = self._detector.score(value, ref)
        return max(0.0, min(1.0, ref_shift * 0.7 + min(1.0, stream_shift / 6.0) * 0.3))


class FeatureQuarantinePolicy:
    def __init__(self) -> None:
        self._quarantined: set[str] = set()

    def evaluate(
        self,
        *,
        feature: str,
        missingness: float,
        drift: float,
        stability: float,
        critical: bool,
    ) -> bool:
        quarantine = False
        if missingness > 0.0 and critical:
            quarantine = True
        if drift > 0.85:
            quarantine = True
        if stability < 0.15 and critical:
            quarantine = True

        if quarantine:
            self._quarantined.add(feature)
        return quarantine

    @property
    def quarantined(self) -> set[str]:
        return set(self._quarantined)


class FeatureStabilityReportBuilder:
    @staticmethod
    def build(
        refs: dict[str, FeatureReference],
        observed: dict[str, float],
        drift_monitor: FeatureDriftMonitor,
        quarantine_policy: FeatureQuarantinePolicy,
        dependencies: dict[str, list[str]],
    ) -> FeatureGovernanceReport:
        by_feature: dict[str, FeatureHealth] = {}
        quarantined: list[str] = []
        critical_issues: list[str] = []

        for feature, ref in refs.items():
            value = observed.get(feature)
            missingness = 1.0 if value is None else 0.0
            drift = drift_monitor.drift(feature, value, ref)
            saturation = 0.0 if value is None else max(0.0, min(1.0, abs(value) / max(abs(ref.upper), 1e-6) - 0.75))

            deps = dependencies.get(feature, [])
            dep_missing = mean([1.0 if observed.get(d) is None else 0.0 for d in deps]) if deps else 0.0
            redundancy = min(1.0, len(deps) * 0.08 + dep_missing * 0.5)

            stability = max(0.0, min(1.0, 1.0 - drift * 0.6 - missingness * 0.5 - saturation * 0.35 - redundancy * 0.25))
            is_quarantined = quarantine_policy.evaluate(
                feature=feature,
                missingness=missingness,
                drift=drift,
                stability=stability,
                critical=ref.critical,
            )

            notes: list[str] = []
            if missingness > 0:
                notes.append("missing")
            if drift > 0.65:
                notes.append("drift_high")
            if saturation > 0.60:
                notes.append("saturation_high")
            if redundancy > 0.65:
                notes.append("dependency_redundancy_high")

            by_feature[feature] = FeatureHealth(
                feature=feature,
                missingness=missingness,
                drift_score=drift,
                stability_score=stability,
                saturation_score=saturation,
                redundancy_score=redundancy,
                quarantined=is_quarantined,
                notes=notes,
            )

            if is_quarantined:
                quarantined.append(feature)
                if ref.critical:
                    critical_issues.append(feature)

        overall_health = mean(h.stability_score for h in by_feature.values()) if by_feature else 1.0
        return FeatureGovernanceReport(
            overall_health=overall_health,
            quarantined_features=sorted(quarantined),
            critical_issues=sorted(set(critical_issues)),
            by_feature=by_feature,
        )


class FeatureGovernance:
    def __init__(self) -> None:
        self._refs: dict[str, FeatureReference] = {}
        self._deps: dict[str, list[str]] = {}
        self._drift = FeatureDriftMonitor()
        self._quarantine = FeatureQuarantinePolicy()

    def register_reference(self, reference: FeatureReference) -> None:
        self._refs[reference.feature] = reference

    def register_dependency(self, feature: str, depends_on: list[str]) -> None:
        self._deps[feature] = depends_on

    def update_observation(self, features: dict[str, float]) -> None:
        self._drift.update(features)

    def evaluate(self, observed: dict[str, float]) -> FeatureGovernanceReport:
        return FeatureStabilityReportBuilder.build(
            refs=self._refs,
            observed=observed,
            drift_monitor=self._drift,
            quarantine_policy=self._quarantine,
            dependencies=self._deps,
        )


__all__ = [
    "DistributionShiftDetector",
    "FeatureDriftMonitor",
    "FeatureGovernance",
    "FeatureQuarantinePolicy",
    "FeatureRunningStats",
    "FeatureStabilityReportBuilder",
]
