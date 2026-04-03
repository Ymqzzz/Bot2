from app.ml.training.evaluator import recommend_ml_improvements


def test_recommend_ml_improvements_for_wrong_prediction():
    plan = recommend_ml_improvements(
        prediction_correct=False,
        confidence=0.92,
        error_magnitude=0.8,
        drift_score=0.6,
        market_regime="high_volatility_trend",
        recent_accuracy=0.49,
    )
    assert plan.prediction_correct is False
    assert any("overconfident errors" in action for action in plan.priority_actions)
    assert any("concept drift" in action for action in plan.priority_actions)
    assert any("walk-forward splits" in action for action in plan.priority_actions)


def test_recommend_ml_improvements_for_right_prediction():
    plan = recommend_ml_improvements(
        prediction_correct=True,
        confidence=0.55,
        error_magnitude=0.0,
        drift_score=0.42,
        market_regime="range_bound",
        recent_accuracy=0.73,
    )
    assert plan.prediction_correct is True
    assert any("calibration" in action for action in plan.priority_actions)
    assert any("drift-aware refresh" in action for action in plan.priority_actions)
    assert any("range_bound" in action for action in plan.priority_actions)
