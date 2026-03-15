from datetime import datetime, timedelta, timezone

from research_core.calibration import ConfidenceCalibrator
from research_core.config import ResearchCoreConfig
from research_core.meta_approval import MetaApprovalEngine
from research_core.meta_features import build_meta_feature_snapshot
from research_core.reliability import compute_brier_score, compute_ece, compute_mce
from research_core.replay_data import align_inputs_to_step_ts, load_replay_stream
from research_core.scenarios import build_feature_toggle_scenario


def test_replay_alignment_no_future_leakage():
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    step_ts = [t0, t1]
    streams = {
        "market_intel": [{"ts": t0, "x": 1}],
        "events": [{"ts": t0, "x": 1}],
        "execution": [{"ts": t1, "x": 2}],
    }
    aligned = align_inputs_to_step_ts(step_ts, streams)
    assert aligned[t0]["execution"] is None
    assert aligned[t1]["execution"]["x"] == 2


def test_scenario_override_isolated():
    s = build_feature_toggle_scenario("s1", {"new_filter": True})
    assert s.feature_toggles["new_filter"] is True
    assert s.parameter_overrides == {}


def test_reliability_metrics():
    probs = [0.2, 0.8, 0.6, 0.4]
    y = [0, 1, 1, 0]
    assert compute_brier_score(probs, y) >= 0
    assert compute_ece(probs, y, num_bins=4) >= 0
    assert compute_mce(probs, y, num_bins=4) >= 0


def test_calibration_fallback_hierarchy():
    cfg = ResearchCoreConfig()
    cal = ConfidenceCalibrator(cfg)
    records = [{"strategy": "core", "raw_confidence": 0.7, "won": 1, "r_multiple": 1.0}] * max(cfg.CALIBRATION_MIN_SAMPLE_SIZE, 30)
    cal.refresh_if_needed(records, force=True)
    snap = cal.get_best_available_snapshot({"strategy": "core", "setup_type": "a", "regime": "trend"})
    assert snap is not None


def test_meta_feature_and_approval_paths():
    cfg = ResearchCoreConfig()
    engine = MetaApprovalEngine(cfg)
    candidate = {"id": "c1", "instrument": "EUR_USD", "strategy": "Squeeze-Breakout", "confidence": 0.6, "ev_r": 0.2}
    features = build_meta_feature_snapshot(candidate, {
        "calibrated_win_prob": 0.55,
        "calibrated_expectancy_proxy": 0.12,
        "execution_feasibility_score": 0.7,
        "regime_support_score": 0.7,
        "event_support_score": 0.7,
        "portfolio_fit_score": 0.7,
        "edge_score": 0.7,
    })
    d = engine.evaluate_candidate(candidate, features, {"scope": "test"})
    assert d.action in {"approve", "approve_downsized", "delay_then_recheck", "reject_soft", "reject_hard"}


def test_meta_hard_reject_logic():
    cfg = ResearchCoreConfig(META_APPROVAL_REJECT_IF_UNCALIBRATED=True)
    engine = MetaApprovalEngine(cfg)
    candidate = {"id": "c2", "instrument": "EUR_USD", "strategy": "Trend-Pullback", "confidence": 0.7, "ev_r": 0.3}
    features = build_meta_feature_snapshot(candidate, {
        "calibrated_win_prob": 0.2,
        "execution_feasibility_score": 0.1,
        "event_support_score": 0.1,
        "portfolio_fit_score": 0.1,
        "edge_score": 0.1,
        "spread_dislocation_risk": 0.9,
    })
    d = engine.evaluate_candidate(candidate, features, {"scope": "test"})
    assert d.action == "reject_hard"


def test_replay_stream_deterministic_flags():
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=5)
    step_ts = [t0, t1]
    streams = {
        "market_intel": [{"ts": t0, "x": 1}],
        "events": [{"ts": t0, "x": 1}],
        "execution": [{"ts": t0, "x": 1}],
    }
    s1 = load_replay_stream(step_ts, streams)
    s2 = load_replay_stream(step_ts, streams)
    assert s1.steps == s2.steps
    assert s1.divergences == s2.divergences
