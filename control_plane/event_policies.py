EVENT_PHASE_POLICIES = {
    "normal": {"allow_breakout": True, "allow_mean_reversion": True, "allow_sweep_reversal": True, "allow_trend_pullback": True, "risk": 1.0, "exec_pen": 1.0},
    "pre_event_lockout": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.6, "exec_pen": 1.4},
    "release_window": {"allow_breakout": True, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.7, "exec_pen": 1.5},
    "post_event_digestion": {"allow_breakout": True, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.8, "exec_pen": 1.2},
    "spread_normalization_pending": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.75, "exec_pen": 1.3},
    "headline_risk": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.6, "exec_pen": 1.6},
}

EVENT_TYPE_OVERRIDES = {
    "POWELL": {"headline_risk_minutes": 60, "post_digest_minutes": 90},
    "FOMC": {"post_digest_minutes": 75},
    "NFP": {"post_digest_minutes": 60},
}
