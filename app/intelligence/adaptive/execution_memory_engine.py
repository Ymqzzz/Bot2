from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_order_style_selector import AdaptiveOrderStyleSelector
from app.intelligence.adaptive.adaptive_types import ExecutionMemoryReport
from app.intelligence.adaptive.fill_quality_archive import FillQualityArchive
from app.intelligence.adaptive.order_tactic_scorecard import OrderTacticScorecard
from app.intelligence.adaptive.session_execution_profile import SessionExecutionProfile


@dataclass
class ExecutionMemoryEngine:
    archive: FillQualityArchive = FillQualityArchive()
    scorecard: OrderTacticScorecard = OrderTacticScorecard()
    session_profile: SessionExecutionProfile = SessionExecutionProfile()
    style_selector: AdaptiveOrderStyleSelector = AdaptiveOrderStyleSelector()

    def evaluate(self, *, context: dict) -> ExecutionMemoryReport:
        summary = self.archive.summarize(list(context.get("execution_records", [])))
        profile = self.session_profile.profile(str(context.get("session", "london")))
        tactic_penalty = self.scorecard.penalty(
            tactic_success=float(context.get("tactic_success", 0.6)),
            adverse_selection=float(context.get("adverse_selection", 0.3)),
        )
        passive_score = clamp(summary["passive_fill_quality"] * profile["passive_bias"] * (1.0 - tactic_penalty * 0.5))
        aggressive_score = clamp(summary["aggressive_fill_quality"] * profile["aggressive_bias"] * (1.0 - tactic_penalty * 0.3))
        style = self.style_selector.choose(passive_score=passive_score, aggressive_score=aggressive_score)

        return ExecutionMemoryReport(
            recommended_order_style=style,
            expected_slippage_bps=summary["expected_slippage_bps"],
            passive_fill_quality=summary["passive_fill_quality"],
            aggressive_fill_quality=summary["aggressive_fill_quality"],
            cancel_success_rate=summary["cancel_success_rate"],
            tactic_penalty=tactic_penalty,
        )
