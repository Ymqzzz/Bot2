from __future__ import annotations

from datetime import datetime
import uuid

from app.intelligence.analog import AnalogEngine
from app.intelligence.adaptive import (
    AdaptiveOperatingLayer,
)
from app.intelligence.base import EngineInput
from app.intelligence.calibrator import ConfidenceCalibrator
from app.intelligence.cross_asset import CrossAssetEngine
from app.intelligence.event_risk import EventRiskEngine
from app.intelligence.instrument_health import InstrumentHealthEngine
from app.intelligence.liquidity import LiquidityEngine
from app.intelligence.models import MarketIntelligenceSnapshot
from app.intelligence.mtf_bias import MultiTimeframeBiasEngine
from app.intelligence.regime import RegimeEngine
from app.intelligence.strategy_health import StrategyHealthEngine
from app.intelligence.structure import StructureEngine
from app.intelligence.sweep import SweepEngine
from app.intelligence.trade_quality import TradeQualityEngine
from app.intelligence.uncertainty import UncertaintyEngine


class IntelligenceOrchestrator:
    def __init__(self):
        self.regime = RegimeEngine()
        self.mtf = MultiTimeframeBiasEngine()
        self.structure = StructureEngine()
        self.liquidity = LiquidityEngine()
        self.sweep = SweepEngine()
        self.event = EventRiskEngine()
        self.instrument_health = InstrumentHealthEngine()
        self.strategy_health = StrategyHealthEngine()
        self.cross_asset = CrossAssetEngine()
        self.uncertainty = UncertaintyEngine()
        self.trade_quality = TradeQualityEngine()
        self.analog = AnalogEngine()
        self.calibrator = ConfidenceCalibrator()
        self.adaptive_layer = AdaptiveOperatingLayer()

    def build_snapshot(
        self,
        *,
        instrument: str,
        bars: list[dict],
        features: dict[str, float],
        context: dict,
        candidate_strategy: str,
        raw_confidence: float,
        timestamp: datetime | None = None,
    ) -> MarketIntelligenceSnapshot:
        ts = timestamp or datetime.utcnow()
        trace_id = context.get("trace_id") or str(uuid.uuid4())
        data = EngineInput(timestamp=ts, instrument=instrument, trace_id=trace_id, bars=bars, features=features, context=context)

        regime = self.regime.compute(data)
        mtf = self.mtf.compute(data)
        structure = self.structure.compute(data)
        liquidity = self.liquidity.compute(data, structure)
        sweep = self.sweep.compute(data, structure, liquidity)
        event_risk = self.event.compute(data)
        inst_health = self.instrument_health.compute(data, structure, event_risk)
        strat_health = self.strategy_health.compute(data)
        cross = self.cross_asset.compute(data, mtf)

        pre_uncertainty = self.uncertainty.compute(
            timestamp=ts,
            instrument=instrument,
            trace_id=trace_id,
            mtf=mtf,
            structure=structure,
            sweep=sweep,
            event_risk=event_risk,
            instrument_health=inst_health,
            strategy_health=strat_health,
            cross_asset=cross,
            analog_confidence=min(1.0, len(context.get("analog_history", [])) / 20.0),
            spread_percentile=float(features.get("spread_percentile", 50.0)),
        )

        quality = self.trade_quality.compute(
            timestamp=ts,
            instrument=instrument,
            trace_id=trace_id,
            calibrated_score=raw_confidence,
            regime=regime,
            mtf=mtf,
            structure=structure,
            liquidity=liquidity,
            sweep=sweep,
            event_risk=event_risk,
            instrument_health=inst_health,
            strategy_health=strat_health,
            cross_asset=cross,
            candidate_strategy=candidate_strategy,
            execution_cost=float(context.get("execution_cost", 0.2)),
            uncertainty=pre_uncertainty,
            portfolio_conflict=float(context.get("portfolio_conflict", 0.0)),
        )
        expected_edge = float(context.get("expected_edge", quality.quality_score - 0.5))
        adaptive_state = self.adaptive_layer.evaluate(
            timestamp=ts,
            instrument=instrument,
            trace_id=trace_id,
            features=features,
            context=context,
            candidate_strategy=candidate_strategy,
            base_confidence=quality.approval_confidence,
            base_size_multiplier=quality.size_multiplier,
            expected_edge=expected_edge,
        )

        base = MarketIntelligenceSnapshot(
            timestamp=ts,
            instrument=instrument,
            trace_id=trace_id,
            confidence=quality.approval_confidence,
            sources=["intelligence_orchestrator"],
            regime=regime,
            mtf_bias=mtf,
            structure=structure,
            liquidity=liquidity,
            sweep=sweep,
            event_risk=event_risk,
            instrument_health=inst_health,
            strategy_health=strat_health,
            cross_asset=cross,
            trade_quality=quality,
            uncertainty=pre_uncertainty,
            adaptive=adaptive_state,
            integrity_flags={},
        )

        analog = self.analog.compute(base, context.get("analog_history", []), candidate_strategy)
        uncertainty = self.uncertainty.compute(
            timestamp=ts,
            instrument=instrument,
            trace_id=trace_id,
            mtf=mtf,
            structure=structure,
            sweep=sweep,
            event_risk=event_risk,
            instrument_health=inst_health,
            strategy_health=strat_health,
            cross_asset=cross,
            analog_confidence=analog.analog_confidence,
            spread_percentile=float(features.get("spread_percentile", 50.0)),
        )
        enriched = MarketIntelligenceSnapshot(**{**base.__dict__, "analog": analog, "uncertainty": uncertainty})
        calib = self.calibrator.compute(enriched, raw_confidence)
        return MarketIntelligenceSnapshot(**{**enriched.__dict__, "calibration": calib})
