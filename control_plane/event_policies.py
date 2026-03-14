EVENT_PHASE_POLICIES = {
    "normal": {"allow_breakout": True, "allow_mean_reversion": True, "allow_sweep_reversal": True, "allow_trend_pullback": True, "risk": 1.0, "exec_penalty": 1.0},
    "pre_event_lockout": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.6, "exec_penalty": 1.25},
    "release_window": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.3, "exec_penalty": 1.7},
    "post_event_digestion": {"allow_breakout": True, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.7, "exec_penalty": 1.25},
    "spread_normalization_pending": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.5, "exec_penalty": 1.5},
    "post_event_tradable": {"allow_breakout": True, "allow_mean_reversion": True, "allow_sweep_reversal": True, "allow_trend_pullback": True, "risk": 0.9, "exec_penalty": 1.1},
    "headline_risk": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.4, "exec_penalty": 1.6},
}

EVENT_TYPE_OVERRIDES = {
    "NFP": {"post_digestion_mult": 1.5},
    "FOMC": {"post_digestion_mult": 1.8, "headline_risk": True},
    "POWELL": {"headline_risk": True},
    "CPI": {"post_digestion_mult": 1.2},
}
