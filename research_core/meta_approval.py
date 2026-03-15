from __future__ import annotations

from uuid import uuid4

from research_core.config import ResearchCoreConfig
from research_core.models import MetaApprovalDecision, MetaFeatureSnapshot
from research_core.reason_codes import *


class MetaApprovalEngine:
    def __init__(self, config: ResearchCoreConfig):
        self.config = config

    def score_candidate(self, meta_features: MetaFeatureSnapshot) -> float:
        return float(max(0.0, min(1.0, meta_features.meta_quality_score)))

    def should_delay(self, meta_features: MetaFeatureSnapshot) -> tuple[bool, int | None]:
        if not self.config.META_APPROVAL_ALLOW_DELAY_MODE:
            return False, None
        spread_risk = float(meta_features.spread_dislocation_risk or 0.0)
        late_risk = float(meta_features.late_entry_risk or 0.0)
        if 0.5 <= spread_risk < 0.8 or 0.5 <= late_risk < 0.8:
            return True, self.config.META_APPROVAL_DEFAULT_DELAY_SECONDS
        return False, None

    def should_downsize(self, meta_features: MetaFeatureSnapshot) -> tuple[bool, float]:
        score = self.score_candidate(meta_features)
        if score >= self.config.META_APPROVAL_MIN_SCORE and score < self.config.META_APPROVAL_MIN_SCORE + 0.1:
            return True, self.config.META_APPROVAL_DOWNSIZE_MULTIPLIER
        return False, 1.0

    def should_reject(self, meta_features: MetaFeatureSnapshot) -> tuple[bool, bool, list[str]]:
        reasons: list[str] = []
        hard = False
        cp = meta_features.calibrated_win_prob
        if cp is None and self.config.META_APPROVAL_REJECT_IF_UNCALIBRATED:
            reasons.append(META_REJECT_UNCALIBRATED_CONFIDENCE)
            hard = True
        if cp is not None and cp < self.config.META_APPROVAL_MIN_CALIBRATED_WIN_PROB:
            reasons.append(META_REJECT_LOW_CALIBRATED_PROB)
            hard = True
        if (meta_features.event_support_score or 1.0) < 0.2:
            reasons.append(META_REJECT_EVENT_CONFLICT)
            hard = hard or self.config.META_APPROVAL_HARD_REJECT_ON_EVENT_CONFLICT
        if (meta_features.execution_feasibility_score or 1.0) < 0.2 or (meta_features.spread_dislocation_risk or 0.0) > 0.8:
            reasons.append(META_REJECT_POOR_EXECUTION)
            if (meta_features.spread_dislocation_risk or 0.0) > 0.8:
                reasons.append(META_REJECT_SPREAD_DISLOCATION)
            hard = hard or self.config.META_APPROVAL_HARD_REJECT_ON_EXECUTION_DISLOCATION
        if (meta_features.portfolio_fit_score or 1.0) < 0.2:
            reasons.append(META_REJECT_POOR_PORTFOLIO_FIT)
            hard = True
        if (meta_features.edge_score or 1.0) < 0.2:
            reasons.append(META_REJECT_EDGE_DECAY)
            hard = True
        if (meta_features.regime_support_score or 1.0) < 0.2:
            reasons.append(META_REJECT_REGIME_CONFLICT)
        if (meta_features.late_entry_risk or 0.0) > 0.8:
            reasons.append(META_REJECT_LATE_ENTRY)
        score = self.score_candidate(meta_features)
        if score < self.config.META_APPROVAL_MIN_SCORE:
            reasons.append(META_REJECT_LOW_META_SCORE)
        return bool(reasons), hard, reasons

    def evaluate_candidate(self, candidate: dict, meta_features: MetaFeatureSnapshot, context: dict) -> MetaApprovalDecision:
        reject, hard, reasons = self.should_reject(meta_features)
        score = self.score_candidate(meta_features)
        delay, delay_seconds = self.should_delay(meta_features)
        downsize, multiplier = self.should_downsize(meta_features)

        if reject:
            action = "reject_hard" if hard else "reject_soft"
        elif delay:
            action = "delay_then_recheck"
            reasons.append(META_DELAY_RECHECK)
        elif downsize:
            action = "approve_downsized"
            reasons.append(META_APPROVE_DOWNSIZED)
        else:
            action = "approve"
            reasons.append(META_APPROVE_STRONG)

        return MetaApprovalDecision(
            decision_id=f"mad-{uuid4().hex[:12]}",
            candidate_id=str(candidate.get("id", "")),
            instrument=str(candidate.get("instrument", "")),
            strategy_name=str(candidate.get("strategy", "")),
            action=action,
            approval_score=score,
            calibrated_win_prob=meta_features.calibrated_win_prob,
            calibrated_expectancy_proxy=meta_features.calibrated_expectancy_proxy,
            risk_adjustment_multiplier=multiplier if action == "approve_downsized" else 1.0,
            delay_seconds=delay_seconds if action == "delay_then_recheck" else None,
            reject=action.startswith("reject"),
            reject_hard=action == "reject_hard",
            reason_codes=reasons,
            diagnostics={"meta_score": score, "context": str(context.get("scope", "live"))},
        )
