from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import SandboxEvaluation
from app.intelligence.adaptive.candidate_feature_registry import CandidateFeatureRegistry
from app.intelligence.adaptive.experimental_plugin_interface import ExperimentalPluginInterface
from app.intelligence.adaptive.paper_mode_isolation_layer import PaperModeIsolationLayer
from app.intelligence.adaptive.sandbox_promotion_policy import SandboxPromotionPolicy


@dataclass
class ResearchSandbox:
    registry: CandidateFeatureRegistry = field(default_factory=CandidateFeatureRegistry)
    promotion_policy: SandboxPromotionPolicy = field(default_factory=SandboxPromotionPolicy)
    paper_isolation: PaperModeIsolationLayer = field(default_factory=PaperModeIsolationLayer)

    def run_plugin(self, plugin: ExperimentalPluginInterface, *, features: dict[str, float], context: dict) -> SandboxEvaluation:
        raw_score = clamp(plugin.evaluate(features, context))
        sanitized = self.paper_isolation.sanitize({"score": raw_score})
        promotion_ready, reasons = self.promotion_policy.evaluate(
            score=raw_score,
            min_samples=int(context.get("sandbox_samples", 0)),
            stability=float(context.get("sandbox_stability", 0.0)),
        )
        self.registry.register(plugin.name, {"score": raw_score, "paper_only": sanitized["live_ordering_allowed"]})
        return SandboxEvaluation(
            paper_mode_only=True,
            candidate_module=plugin.name,
            score=raw_score,
            promotion_ready=promotion_ready,
            promotion_reasons=reasons,
        )
