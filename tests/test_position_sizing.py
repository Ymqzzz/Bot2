from app.risk.sizing import PositionSizer


def _compute(sizer: PositionSizer, **kwargs):
    defaults = dict(
        side="BUY",
        nav=100_000.0,
        entry_price=1.1000,
        stop_loss=1.0970,
        atr=0.0010,
        dislocation=1.0,
        spread_pctile=20.0,
        confidence=0.8,
        open_positions=[],
        daily_risk_pct=0.015,
        cluster_risk_pct=0.01,
    )
    defaults.update(kwargs)
    return sizer.compute_units(**defaults)


def test_spread_and_confidence_monotonicity_reduce_units():
    sizer = PositionSizer()

    baseline = _compute(sizer)
    wider_spread = _compute(sizer, spread_pctile=90.0)
    weaker_confidence = _compute(sizer, confidence=0.3)

    assert abs(wider_spread.signed_units) < abs(baseline.signed_units)
    assert abs(weaker_confidence.signed_units) < abs(baseline.signed_units)


def test_tighter_stop_reduces_units_for_same_risk_budget():
    sizer = PositionSizer()

    wider_stop = _compute(sizer, stop_loss=1.0960)  # 40 pips risk
    tighter_stop = _compute(sizer, stop_loss=1.0990)  # 10 pips risk

    assert abs(tighter_stop.signed_units) < abs(wider_stop.signed_units)


def test_units_respect_cap_and_emit_cap_diagnostics():
    sizer = PositionSizer(max_notional_nav_multiple=0.001)

    out = _compute(
        sizer,
        nav=1_000_000.0,
        entry_price=0.5,
        stop_loss=0.1,
        atr=0.0002,
        confidence=1.0,
        spread_pctile=1.0,
        dislocation=1.0,
    )

    assert abs(out.signed_units) <= out.max_units_cap
    assert out.capped is True


def test_intelligence_multipliers_affect_units():
    sizer = PositionSizer()
    baseline = _compute(sizer)
    penalized = _compute(sizer, quality_multiplier=0.4, uncertainty_multiplier=0.5, strategy_health_multiplier=0.6)
    boosted = _compute(sizer, quality_multiplier=1.2, uncertainty_multiplier=1.0, strategy_health_multiplier=1.1)

    assert abs(penalized.signed_units) < abs(baseline.signed_units)
    assert abs(boosted.signed_units) > abs(baseline.signed_units)


def test_strategy_health_and_open_risk_reduce_units():
    sizer = PositionSizer()
    baseline = _compute(sizer, strategy_health_multiplier=1.0)
    unhealthy_strategy = _compute(sizer, strategy_health_multiplier=0.3)
    with_open_risk = _compute(
        sizer,
        open_positions=[{"units": 10_000, "entry_price": 1.1000, "stop_loss": 1.0950}],
    )

    assert abs(unhealthy_strategy.signed_units) < abs(baseline.signed_units)
    assert abs(with_open_risk.signed_units) < abs(baseline.signed_units)
    assert with_open_risk.open_risk_pct > 0.0
