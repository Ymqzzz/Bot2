from app.ml.pair_selector import PairSelectionModel


def _payload() -> dict[str, float]:
    return {
        "confidence": 0.72,
        "confluence": 0.68,
        "setup_recent_perf": 0.63,
        "instrument_recent_perf": 0.61,
        "spread_norm": 0.15,
        "volatility_burst": 0.05,
        "previous_entry_quality": 0.7,
    }


def test_score_uses_confidence_ramp_for_small_samples() -> None:
    model = PairSelectionModel(confidence_floor=0.3, confidence_sample_scale=20)
    baseline = model.score("EUR_USD", _payload())
    for _ in range(40):
        model.learn("EUR_USD", _payload(), realized_result=0.35)
    seasoned = model.score("EUR_USD", _payload())
    assert seasoned.pair_score > baseline.pair_score


def test_expected_result_is_shrunk_by_bayesian_prior() -> None:
    conservative = PairSelectionModel(bayesian_prior_mean=0.0, bayesian_prior_strength=40.0)
    aggressive = PairSelectionModel(bayesian_prior_mean=0.0, bayesian_prior_strength=1.0)
    for _ in range(5):
        conservative.learn("GBP_USD", _payload(), realized_result=0.9)
        aggressive.learn("GBP_USD", _payload(), realized_result=0.9)
    conservative_signal = conservative.score("GBP_USD", _payload())
    aggressive_signal = aggressive.score("GBP_USD", _payload())
    assert conservative_signal.expected_result < aggressive_signal.expected_result


def test_downside_penalty_reduces_pair_score() -> None:
    model = PairSelectionModel(downside_penalty_weight=0.6)
    for r in [0.6, 0.5, -1.1, -0.9, 0.55, -0.8]:
        model.learn("USD_JPY", _payload(), realized_result=r)
    penalized = model.score("USD_JPY", _payload())

    less_penalty_model = PairSelectionModel(downside_penalty_weight=0.0)
    for r in [0.6, 0.5, -1.1, -0.9, 0.55, -0.8]:
        less_penalty_model.learn("USD_JPY", _payload(), realized_result=r)
    unpenalized = less_penalty_model.score("USD_JPY", _payload())
    assert penalized.pair_score < unpenalized.pair_score
