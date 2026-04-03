from __future__ import annotations

INVALIDATION_RULES = {
    "directional_trend": "break_structure_against_direction",
    "liquidity_sweep": "failed_reclaim_after_sweep",
    "volatility_expansion": "breakout_returns_to_range_with_low_followthrough",
    "orderflow_continuation": "delta_divergence_and_absorption_flip",
    "mean_reversion_snapback": "impulse_continuation_beyond_reversion_zone",
    "macro_alignment": "macro_proxy_reverses_beyond_threshold",
    "behavioral_squeeze": "squeeze_fails_and_open_interest_normalizes",
}
