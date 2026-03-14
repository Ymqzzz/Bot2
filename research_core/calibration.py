from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from research_core.config import ResearchCoreConfig
from research_core.models import CalibrationBin, CalibrationSnapshot
from research_core.reason_codes import (
    CALIBRATION_FALLBACK_GLOBAL,
    CALIBRATION_METHOD_BINNED,
    CALIBRATION_METHOD_ISOTONIC,
    CALIBRATION_METHOD_PLATT,
    CALIBRATION_SAMPLE_LOW,
    CALIBRATION_SEGMENT_HEALTHY,
    CALIBRATION_SEGMENT_WEAK,
)
from research_core.reliability import compute_brier_score, compute_ece, compute_mce


class ConfidenceCalibrator:
    def __init__(self, config: ResearchCoreConfig):
        self.config = config
        self.snapshots: dict[tuple[str, str], CalibrationSnapshot] = {}

    def fit_calibration(self, scope_type: str, scope_key: str, historical_records: list[dict]) -> CalibrationSnapshot:
        size = len(historical_records)
        probs = [float(r["raw_confidence"]) for r in historical_records]
        outcomes = [int(bool(r["won"])) for r in historical_records]
        expectancy = [float(r.get("r_multiple", 0.0)) for r in historical_records]
        bins = self._build_bins(probs, outcomes, expectancy)
        brier = compute_brier_score(probs, outcomes) if size else None
        ece = compute_ece(probs, outcomes, self.config.CALIBRATION_NUM_BINS) if size else None
        mce = compute_mce(probs, outcomes, self.config.CALIBRATION_NUM_BINS) if size else None
        reason_codes = [self._method_code()]
        if size < self.config.CALIBRATION_MIN_SAMPLE_SIZE:
            reason_codes.append(CALIBRATION_SAMPLE_LOW)
            reason_codes.append(CALIBRATION_SEGMENT_WEAK)
        else:
            reason_codes.append(CALIBRATION_SEGMENT_HEALTHY)
        snapshot = CalibrationSnapshot(
            calibration_id=f"cal-{uuid4().hex[:10]}",
            scope_type=scope_type,
            scope_key=scope_key,
            sample_size=size,
            calibration_method=self.config.CALIBRATION_METHOD.value,
            reliability_score=max(0.0, 1.0 - float(ece or 1.0)),
            brier_score=brier,
            ece_score=ece,
            mce_score=mce,
            bins=bins,
            mapping_params={"method": self.config.CALIBRATION_METHOD.value},
            fresh_asof=datetime.now(timezone.utc),
            reason_codes=reason_codes,
        )
        self.snapshots[(scope_type, scope_key)] = snapshot
        return snapshot

    def predict_calibrated_prob(self, raw_score: float, scope_context: dict[str, str]) -> float | None:
        snapshot = self.get_best_available_snapshot(scope_context)
        if snapshot is None:
            return None
        if not snapshot.bins:
            return max(0.0, min(1.0, raw_score))
        for b in snapshot.bins:
            if b.score_min <= raw_score <= b.score_max:
                return b.empirical_win_rate
        return snapshot.bins[-1].empirical_win_rate

    def predict_expectancy_proxy(self, raw_score: float, scope_context: dict[str, str]) -> float | None:
        snapshot = self.get_best_available_snapshot(scope_context)
        if snapshot is None:
            return None
        for b in snapshot.bins:
            if b.score_min <= raw_score <= b.score_max:
                return b.empirical_expectancy_r
        return snapshot.bins[-1].empirical_expectancy_r if snapshot.bins else None

    def refresh_if_needed(self, historical_records: list[dict], force: bool = False) -> list[CalibrationSnapshot]:
        snapshots: list[CalibrationSnapshot] = []
        if not force and len(historical_records) < self.config.CALIBRATION_REFRESH_TRADES:
            return snapshots
        by_strategy: dict[str, list[dict]] = defaultdict(list)
        for row in historical_records:
            by_strategy[str(row.get("strategy", "global"))].append(row)
        for strategy, rows in by_strategy.items():
            snapshots.append(self.fit_calibration("strategy", strategy, rows))
        snapshots.append(self.fit_calibration("global", "global", historical_records))
        return snapshots

    def get_best_available_snapshot(self, scope_context: dict[str, str]) -> CalibrationSnapshot | None:
        candidate_keys = [
            ("strategy_setup_regime", f"{scope_context.get('strategy')}|{scope_context.get('setup_type')}|{scope_context.get('regime')}"),
            ("strategy_setup", f"{scope_context.get('strategy')}|{scope_context.get('setup_type')}"),
            ("strategy_regime", f"{scope_context.get('strategy')}|{scope_context.get('regime')}"),
            ("strategy", str(scope_context.get("strategy"))),
            ("global", "global"),
        ]
        for k in candidate_keys:
            snap = self.snapshots.get(k)
            if snap and snap.sample_size >= self.config.CALIBRATION_MIN_SAMPLE_SIZE:
                return snap
        global_snap = self.snapshots.get(("global", "global"))
        if global_snap:
            if CALIBRATION_FALLBACK_GLOBAL not in global_snap.reason_codes:
                global_snap.reason_codes.append(CALIBRATION_FALLBACK_GLOBAL)
        return global_snap

    def _method_code(self) -> str:
        if self.config.CALIBRATION_METHOD.value == "isotonic":
            return CALIBRATION_METHOD_ISOTONIC
        if self.config.CALIBRATION_METHOD.value == "platt":
            return CALIBRATION_METHOD_PLATT
        return CALIBRATION_METHOD_BINNED

    def _build_bins(self, probs: list[float], outcomes: list[int], expectancy: list[float]) -> list[CalibrationBin]:
        if not probs:
            return []
        width = 1.0 / self.config.CALIBRATION_NUM_BINS
        buckets: dict[int, list[int]] = defaultdict(list)
        for idx, p in enumerate(probs):
            buckets[min(self.config.CALIBRATION_NUM_BINS - 1, int(max(0.0, min(0.999999, p)) / width))].append(idx)
        bins: list[CalibrationBin] = []
        for b in range(self.config.CALIBRATION_NUM_BINS):
            members = buckets.get(b, [])
            if not members:
                continue
            pvals = [probs[i] for i in members]
            yvals = [outcomes[i] for i in members]
            evals = [expectancy[i] for i in members]
            avg_pred = sum(pvals) / len(pvals)
            avg_obs = sum(yvals) / len(yvals)
            bins.append(CalibrationBin(
                bin_id=f"b{b}",
                score_min=b * width,
                score_max=min(1.0, (b + 1) * width),
                count=len(members),
                avg_raw_score=avg_pred,
                empirical_win_rate=avg_obs,
                empirical_expectancy_r=sum(evals) / len(evals),
                avg_mfe_r=None,
                avg_mae_r=None,
                brier_component=sum((p - y) ** 2 for p, y in zip(pvals, yvals)) / len(yvals),
                ece_component=abs(avg_pred - avg_obs),
            ))
        return bins
