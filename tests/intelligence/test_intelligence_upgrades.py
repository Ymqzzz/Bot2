from datetime import datetime

from app.intelligence.orchestrator import IntelligenceOrchestrator
from app.risk.sizing import PositionSizer


def _bars(mode: str, n: int = 180):
    out = []
    px = 1.10
    for i in range(n):
        if mode == "trend":
            px += 0.00025
            wiggle = 0.00015
        elif mode == "chop":
            px += 0.00005 if i % 2 == 0 else -0.00005
            wiggle = 0.00025
        else:
            px += 0.00002
            wiggle = 0.00012
        out.append({"open": px - wiggle / 2, "high": px + wiggle, "low": px - wiggle, "close": px})
    return out


def test_trade_quality_clean_setup_outranks_messy_setup() -> None:
    orch = IntelligenceOrchestrator()
    aligned = orch.build_snapshot(
        instrument="EURUSD",
        bars=_bars("trend"),
        features={"bar_overlap": 0.15, "directional_persistence": 0.85, "spread_percentile": 12.0},
        context={"strategy_performance": {"trend": {"sample_size": 90, "win_rate": 0.64, "expectancy": 0.25}}, "cross_asset": {}, "analog_history": []},
        candidate_strategy="trend",
        raw_confidence=0.72,
        timestamp=datetime(2026, 1, 1),
    )
    messy = orch.build_snapshot(
        instrument="EURUSD",
        bars=_bars("chop"),
        features={"bar_overlap": 0.8, "directional_persistence": 0.3, "spread_percentile": 70.0},
        context={"near_event": True, "event_severity": 0.9, "event_relevance": 0.9, "strategy_performance": {"trend": {"sample_size": 12, "win_rate": 0.45, "expectancy": -0.1}}, "cross_asset": {}, "analog_history": []},
        candidate_strategy="trend",
        raw_confidence=0.72,
        timestamp=datetime(2026, 1, 1),
    )

    assert aligned.trade_quality.trade_quality_score > messy.trade_quality.trade_quality_score
    assert messy.uncertainty.uncertainty_score > aligned.uncertainty.uncertainty_score


def test_liquidity_significance_not_proximity_only() -> None:
    orch = IntelligenceOrchestrator()
    snap = orch.build_snapshot(
        instrument="GBPUSD",
        bars=_bars("trend", 120),
        features={"bar_overlap": 0.25, "directional_persistence": 0.75, "spread_percentile": 20.0},
        context={"strategy_performance": {}, "cross_asset": {}, "analog_history": []},
        candidate_strategy="trend",
        raw_confidence=0.6,
    )
    nearest = snap.liquidity.nearest_zones[0]
    top = snap.liquidity.all_pools[0]
    assert top.significance_score >= nearest.significance_score


def test_sizing_respects_uncertainty_multiplier() -> None:
    sizer = PositionSizer()
    hi = sizer.compute_units(
        side="BUY", nav=100000, entry_price=1.1, stop_loss=1.098, atr=0.001, dislocation=1.0,
        spread_pctile=20, confidence=0.7, open_positions=[], daily_risk_pct=0.01, cluster_risk_pct=0.01,
        quality_multiplier=1.0, uncertainty_multiplier=1.0, strategy_multiplier=1.0,
    )
    low = sizer.compute_units(
        side="BUY", nav=100000, entry_price=1.1, stop_loss=1.098, atr=0.001, dislocation=1.0,
        spread_pctile=20, confidence=0.7, open_positions=[], daily_risk_pct=0.01, cluster_risk_pct=0.01,
        quality_multiplier=1.0, uncertainty_multiplier=0.5, strategy_multiplier=1.0,
    )
    assert abs(low.signed_units) < abs(hi.signed_units)
