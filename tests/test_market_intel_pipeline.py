from datetime import datetime

import pytest

from market_intel.pipeline import (
    DependencyOrderedMarketIntelPipeline,
    LegacyMarketIntelPipeline,
    MarketIntelPipeline,
    MarketIntelPipelineError,
)
from market_intel.models import MarketIntelSnapshot, SessionContext
from market_intel.pipeline import (
    DependencyOrderedMarketIntelPipeline,
    LegacyMarketIntelPipeline,
    MarketIntelPipeline,
    MarketIntelPipelineError,
)


def test_to_flat_dict_flattens_dataclass_tree() -> None:
    snapshot = MarketIntelSnapshot(
        session=SessionContext(instrument="EURUSD", asof=datetime(2026, 1, 1)),
        metadata={"source": "unit"},
    )

    flat = snapshot.to_flat_dict()

    assert flat["session.instrument"] == "EURUSD"
    assert flat["metadata.source"] == "unit"


def test_pipeline_alias_points_to_dependency_ordered_runtime() -> None:
    assert MarketIntelPipeline is DependencyOrderedMarketIntelPipeline
    assert MarketIntelPipeline is not LegacyMarketIntelPipeline


def test_pipeline_non_strict_failure_is_recorded() -> None:
    pipeline = MarketIntelPipeline(providers={"htf_structure": lambda *_: (_ for _ in ()).throw(ValueError("boom"))})

    snapshot = pipeline.build_snapshot("EURUSD", datetime(2026, 1, 1), runtime_context={"strict_mode": False})

    failed = [status for status in snapshot.provider_status if not status.ok and status.provider == "htf_structure"]
    assert failed
    assert snapshot.metadata["pipeline_class"] == "DependencyOrderedMarketIntelPipeline"


def test_pipeline_strict_failure_raises() -> None:
    pipeline = MarketIntelPipeline(providers={"execution_quality": lambda *_: (_ for _ in ()).throw(ValueError("boom"))})

    with pytest.raises(MarketIntelPipelineError):
        pipeline.build_snapshot("EURUSD", datetime(2026, 1, 1), runtime_context={"strict_mode": False, "strict_dependencies": ["execution_quality"]})


def test_market_intel_pipeline_alias_points_to_dependency_ordered() -> None:
    assert MarketIntelPipeline is DependencyOrderedMarketIntelPipeline
    assert MarketIntelPipeline is not LegacyMarketIntelPipeline


def test_pipeline_retries_recover_transient_provider_failures() -> None:
    calls = {"count": 0}

    def flaky_provider(*_args):
        calls["count"] += 1
        if calls["count"] < 2:
            raise ConnectionError("temporary disconnect")
        return {"ok": True}

    pipeline = MarketIntelPipeline(providers={"htf_structure": flaky_provider})
    snapshot = pipeline.build_snapshot(
        "EURUSD",
        datetime(2026, 1, 1),
        runtime_context={"provider_retry_attempts": 3, "provider_backoff_ms": 0},
    )

    status = next(s for s in snapshot.provider_status if s.provider == "htf_structure")
    assert status.ok
    assert calls["count"] == 2
    assert snapshot.metadata["connectivity"]["retry_attempts"] == 3


def test_pipeline_opens_circuit_for_repeated_failures() -> None:
    def dead_provider(*_args):
        raise TimeoutError("provider down")

    pipeline = MarketIntelPipeline(providers={"htf_structure": dead_provider})
    runtime_context = {
        "provider_retry_attempts": 1,
        "provider_backoff_ms": 0,
        "provider_circuit_breaker_threshold": 1,
        "provider_circuit_breaker_cooldown_s": 60,
    }
    first = pipeline.build_snapshot("EURUSD", datetime(2026, 1, 1), runtime_context=runtime_context)
    second = pipeline.build_snapshot("EURUSD", datetime(2026, 1, 1), runtime_context=runtime_context)

    first_status = next(s for s in first.provider_status if s.provider == "htf_structure")
    second_status = next(s for s in second.provider_status if s.provider == "htf_structure")
    assert "TimeoutError" in (first_status.reason or "")
    assert "circuit_open_until" in (second_status.reason or "")
