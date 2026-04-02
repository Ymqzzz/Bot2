import numpy as np

from app.ml.feature_schema import FEATURE_SPECS
from app.ml.state_builder import NormalizationStats, StateBuilder


def test_state_shape_stability_and_missing_masking():
    builder = StateBuilder(NormalizationStats(version="v1", mean={}, std={}))
    state = builder.build(
        market_state={"ret_1": 0.1},
        signal_state={},
        risk_state={},
        execution_state={},
        context_state={},
    )
    assert state.values.shape[0] == len(FEATURE_SPECS)
    assert state.missing_mask.shape[0] == len(FEATURE_SPECS)
    assert np.isclose(state.values[0], 0.1)
    assert state.missing_mask.sum() >= 1
