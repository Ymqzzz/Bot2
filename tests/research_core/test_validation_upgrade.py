from research_core.validation import (
    apply_embargo,
    purged_time_splits,
    robustness_surface,
    run_ablation,
    run_stress_replay,
    sharpe_by_regime,
    validation_report_bundle,
)


def test_purged_split_and_embargo():
    splits = purged_time_splits(size=100, folds=5, purge=2)
    assert len(splits) == 5
    allowed = apply_embargo([10, 20], embargo=1, max_index=30)
    assert 10 not in allowed
    assert 9 not in allowed
    assert 11 not in allowed


def test_ablation_and_surface_and_regime_report():
    ab = run_ablation(["trend", "mean_rev"], lambda engines: float(len(engines)))
    assert ab["baseline"] == 2.0
    assert ab["drop_trend"] == 1.0

    surface = robustness_surface({"a": [1.0, 2.0], "b": [3.0]}, lambda p: p["a"] + p["b"])
    assert len(surface) == 2

    sharpe = sharpe_by_regime([("trend", 1.0), ("trend", 0.5), ("range", -0.2), ("range", 0.1)])
    assert "trend" in sharpe
    assert "range" in sharpe


def test_stress_and_report_bundle():
    stress = run_stress_replay([0.1, -0.2, 0.05], shocks=[-0.1, 0.0])
    assert "stressed_expectancy" in stress
    bundle = validation_report_bundle(
        [("trend", 0.1), ("trend", 0.2), ("range", -0.1), ("range", 0.0)],
        [0.1, -0.2, 0.05],
        [-0.1, 0.0],
    )
    assert "sharpe_by_regime" in bundle
    assert "stress" in bundle
