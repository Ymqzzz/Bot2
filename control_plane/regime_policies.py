REGIME_POLICIES = {
    "trend_expansion": {"allowed": ["Trend-Pullback", "Breakout-Squeeze", "Squeeze-Breakout"], "blocked": ["Range-MeanReversion"]},
    "rotation_mean_reversion": {"allowed": ["Range-MeanReversion", "Liquidity-Sweep-Reversal"], "blocked": ["Breakout-Squeeze"]},
    "dead_zone": {"allowed": ["Liquidity-Sweep-Reversal"], "blocked": ["Breakout-Squeeze", "Squeeze-Breakout"]},
    "uncertain_mixed": {"allowed": ["Trend-Pullback", "Liquidity-Sweep-Reversal"], "blocked": []},
}
