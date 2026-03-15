from datetime import datetime

import pytest

from market_intel.pipeline import (
    DependencyOrderedMarketIntelPipeline,
    LegacyMarketIntelPipeline,
    MarketIntelPipeline,
    MarketIntelPipelineError,
)
from market_intel.models import MarketIntelSnapshot, SessionContext


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
