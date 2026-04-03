from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adaptive_weight_updater import AdaptiveWeightUpdater
from .engine_scorecard import EngineScorecard


@dataclass(slots=True)
class AttributionResult:
    engine_trust: dict[str, float]
    labels: list[str]


class LiveAttributionEngine:
    def __init__(self):
        self.scorecard = EngineScorecard()
        self.updater = AdaptiveWeightUpdater()

    def process_closed_trade(self, trade_context: dict[str, Any], close_info: dict[str, Any]) -> AttributionResult:
        predicted_edge = float(trade_context.get("ev_r", 0.0))
        realized_r = float(close_info.get("realized_r", 0.0))
        regime = str(trade_context.get("regime", "unknown"))
        session = str(trade_context.get("session", "unknown"))
        instrument = str(trade_context.get("instrument", "unknown"))
        labels: list[str] = []
        trusts: dict[str, float] = {}

        for engine in trade_context.get("supporting_engines", []):
            trust = self.updater.update(
                self.scorecard,
                str(engine),
                realized_r,
                predicted_edge,
                regime=regime,
                session=session,
                instrument=instrument,
            )
            trusts[str(engine)] = trust
            if realized_r > 0:
                labels.append("ATTR_GOOD_CALL")
            elif predicted_edge > 0 and realized_r < 0:
                labels.append("ATTR_BAD_CALL")
        for engine in trade_context.get("opposing_engines", []):
            # Opposing engines get inverse contribution for attribution.
            trust = self.updater.update(
                self.scorecard,
                str(engine),
                -realized_r,
                -predicted_edge,
                regime=regime,
                session=session,
                instrument=instrument,
            )
            trusts[str(engine)] = trust
            if realized_r < 0:
                labels.append("ATTR_OPPOSER_WAS_RIGHT")

        if not trusts:
            labels.append("ATTRIBUTION_NO_ENGINE_DATA")

        delta = abs(realized_r - predicted_edge)
        if delta > 1.2:
            labels.append("ATTR_LUCK_UNLUCKY_DEVIATION")
        if realized_r > 0 and predicted_edge < 0:
            labels.append("ATTR_UNLIKELY_WIN")
        if realized_r < 0 and predicted_edge > 0.4 and delta > 0.8:
            labels.append("ATTR_MODEL_OVERCONFIDENT")

        return AttributionResult(engine_trust=trusts, labels=labels)
