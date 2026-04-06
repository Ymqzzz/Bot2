from datetime import datetime

from app.intelligence.base import EngineInput
from app.intelligence.institutional.ensemble_coordination import EnsembleCoordinator, FamilyConfidenceAggregator, ThesisFamilyModel
from app.intelligence.institutional.schemas import Direction, ThesisVote
from app.intelligence.regime import RegimeEngine


def test_regime_engine_uses_algorithmic_price_action_identifier() -> None:
    engine = RegimeEngine()
    snapshot = engine.compute(
        EngineInput(
            timestamp=datetime(2026, 1, 1),
            instrument="EURUSD",
            trace_id="trace-pa",
            bars=[],
            context={"near_event": False},
            features={
                "atr_percentile": 0.68,
                "realized_vol": 0.42,
                "bar_overlap": 0.28,
                "directional_persistence": 0.76,
                "breakout_follow_through": 0.82,
                "spread_percentile": 0.22,
                "directional_efficiency": 0.83,
                "range_compression": 0.25,
                "price_action_trend_score": 0.74,
                "price_action_mean_revert_score": 0.21,
                "price_action_breakout_score": 0.88,
                "price_action_confidence": 0.84,
                "price_action_id": 3.0,
            },
        )
    )

    assert snapshot.label == "algorithmic_breakout_expansion"
    assert 0.0 <= snapshot.confidence <= 1.0
    rationale_codes = {e.code for e in snapshot.rationale}
    assert "price_action_confidence" in rationale_codes


def test_family_aggregator_and_ensemble_favor_consistent_family() -> None:
    votes = [
        ThesisVote(source="trend_a", thesis_family="trend_following", direction=Direction.LONG, confidence=0.92, weight=1.0),
        ThesisVote(source="trend_b", thesis_family="trend_following", direction=Direction.LONG, confidence=0.87, weight=0.9),
        ThesisVote(source="mean_a", thesis_family="mean_reversion", direction=Direction.SHORT, confidence=0.54, weight=0.6),
        ThesisVote(source="mean_b", thesis_family="mean_reversion", direction=Direction.FLAT, confidence=0.45, weight=0.4),
    ]

    family = FamilyConfidenceAggregator().aggregate(votes)
    assert family
    assert family[0].thesis_family == "trend_following"
    assert family[0].area_specialty == "directional continuation and pullback entries"
    assert family[0].confidence > family[1].confidence

    ensemble = EnsembleCoordinator().combine(votes)
    assert ensemble.net_direction == Direction.LONG
    assert 0.0 <= ensemble.inter_family_conflict <= 1.0
    assert 0.0 <= ensemble.confidence <= 1.0


def test_thesis_family_model_exposes_area_specialty_for_each_family() -> None:
    model = ThesisFamilyModel()
    families = [
        "trend_following",
        "mean_reversion",
        "liquidity_sweep",
        "breakout_continuation",
        "event_reaction",
        "volatility_expansion",
        "other",
    ]

    for family in families:
        specialty = model.specialty_of(family)
        assert isinstance(specialty, str)
        assert specialty
