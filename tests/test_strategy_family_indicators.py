from app.strategy.plugins.breakout_plugin import BreakoutPlugin
from app.strategy.plugins.mean_reversion_plugin import MeanReversionPlugin
from app.strategy.plugins.momentum_pulse_plugin import MomentumPulsePlugin
from app.strategy.plugins.pullback_reclaim_plugin import PullbackReclaimPlugin
from app.strategy.plugins.trend_plugin import TrendPlugin


def _sample_bars() -> list[dict]:
    bars: list[dict] = []
    px = 1.0
    for _ in range(40):
        px += 0.0003
        bars.append({"open": px - 0.0001, "high": px + 0.00025, "low": px - 0.00025, "close": px})
    return bars


def test_each_strategy_family_uses_expanded_indicator_set() -> None:
    bars = _sample_bars()
    px = float(bars[-1]["close"])

    trend = TrendPlugin().generate(
        "EUR_USD",
        bars,
        {"ema_slope": 0.00022, "trend_alignment": 0.44, "trend_consistency": 0.28, "atr": 0.0006},
    )
    assert trend is not None
    assert {"ema_slope", "trend_alignment", "trend_consistency"} <= set(trend.metadata)

    mean_rev = MeanReversionPlugin().generate(
        "EUR_USD",
        bars,
        {"zscore": 2.1, "reversion_pressure": 0.45, "chop_regime": 0.55, "atr": 0.0006},
    )
    assert mean_rev is not None
    assert {"zscore", "reversion_pressure", "chop_regime"} <= set(mean_rev.metadata)

    breakout_bars = bars[:-1] + [
        {"open": px, "high": px + 0.003, "low": px - 0.0002, "close": px + 0.002},
    ]
    breakout = BreakoutPlugin().generate(
        "EUR_USD",
        breakout_bars,
        {"atr": 0.0007, "breakout_pressure": 0.7, "range_compression": 0.2},
    )
    assert breakout is not None
    assert {"range_hi", "range_lo", "breakout_pressure", "range_compression"} <= set(breakout.metadata)

    momentum = MomentumPulsePlugin().generate(
        "EUR_USD",
        bars,
        {"momentum": 0.9, "trend_regime": 0.7, "impulse_strength": 0.6, "breakout_pressure": 0.52, "atr": 0.0006},
    )
    assert momentum is not None
    assert {"momentum", "trend_regime", "impulse_strength", "breakout_pressure"} <= set(momentum.metadata)

    pullback = PullbackReclaimPlugin().generate(
        "EUR_USD",
        bars,
        {
            "ema_fast": 1.2,
            "ema_slow": 1.1,
            "zscore": -0.8,
            "trend_regime": 0.72,
            "pullback_quality": 0.63,
            "trend_alignment": 0.2,
            "atr": 0.0007,
        },
    )
    assert pullback is not None
    assert {"zscore", "trend_regime", "pullback_quality", "trend_alignment"} <= set(pullback.metadata)
