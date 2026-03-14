from __future__ import annotations

EVENT_PHASE_POLICIES = {
    "normal": {"allow_breakout": True, "allow_mean_reversion": True, "allow_sweep_reversal": True, "allow_trend_pullback": True, "risk": 1.0, "exec_pen": 1.0},
    "pre_event_lockout": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.75, "exec_pen": 1.4},
    "release_window": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": False, "risk": 0.5, "exec_pen": 2.0},
    "post_event_digestion": {"allow_breakout": True, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.8, "exec_pen": 1.4},
    "spread_normalization_pending": {"allow_breakout": True, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.7, "exec_pen": 1.6},
    "post_event_tradable": {"allow_breakout": True, "allow_mean_reversion": True, "allow_sweep_reversal": True, "allow_trend_pullback": True, "risk": 0.95, "exec_pen": 1.1},
    "headline_risk": {"allow_breakout": False, "allow_mean_reversion": False, "allow_sweep_reversal": False, "allow_trend_pullback": True, "risk": 0.6, "exec_pen": 1.8},
}

EVENT_TYPE_OVERRIDES = {
    "CPI": {"post_digest_minutes": 30},
    "PPI": {"post_digest_minutes": 30},
    "GDP": {"post_digest_minutes": 30},
    "NFP": {"post_digest_minutes": 60, "exec_penalty_mult": 1.2},
    "LABOR": {"post_digest_minutes": 60, "exec_penalty_mult": 1.15},
    "FOMC": {"post_digest_minutes": 90, "headline_risk_minutes": 120, "exec_penalty_mult": 1.3},
    "POWELL": {"headline_risk_minutes": 180, "allow_mean_reversion": False},
}
