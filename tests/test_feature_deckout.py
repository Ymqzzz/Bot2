from app.features.price_features import compute_price_features


def test_compute_price_features_emits_rich_runtime_keys() -> None:
    bars = []
    px = 1.0000
    for i in range(120):
        px += 0.0003 if i % 5 else -0.0001
        bars.append(
            {
                "open": px - 0.0002,
                "high": px + 0.0004,
                "low": px - 0.0004,
                "close": px,
            }
        )

    feats = compute_price_features(bars)

    for key in (
        "ret_1",
        "ret_3",
        "ret_12",
        "realized_vol",
        "trend_slope",
        "momentum",
        "vwap_distance",
        "daily_range_pos",
        "prev_day_hilo_proximity",
        "liquidity_sweep",
        "bos",
        "trend_regime",
        "chop_regime",
        "confluence",
        "confidence",
        "directional_efficiency",
        "range_compression",
        "wick_rejection_bias",
        "price_action_trend_score",
        "price_action_mean_revert_score",
        "price_action_breakout_score",
        "price_action_confidence",
        "price_action_id",
        "trend_alignment",
        "trend_consistency",
        "reversion_pressure",
        "breakout_pressure",
        "range_compression",
        "impulse_strength",
        "pullback_quality",
    ):
        assert key in feats

    assert 0.0 <= feats["confidence"] <= 1.0
    assert 0.0 <= feats["trend_regime"] <= 1.0
    assert 0.0 <= feats["chop_regime"] <= 1.0
    assert 0.0 <= feats["price_action_confidence"] <= 1.0
    assert feats["price_action_id"] in {1.0, 2.0, 3.0}
    assert -1.0 <= feats["trend_alignment"] <= 1.0
    assert 0.0 <= feats["trend_consistency"] <= 1.0
    assert 0.0 <= feats["reversion_pressure"] <= 1.0
    assert 0.0 <= feats["breakout_pressure"] <= 1.0
    assert 0.0 <= feats["range_compression"] <= 1.0
    assert 0.0 <= feats["impulse_strength"] <= 1.0
    assert 0.0 <= feats["pullback_quality"] <= 1.0
