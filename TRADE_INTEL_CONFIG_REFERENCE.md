# Trade Intel Config Reference

All environment variables are loaded in `trade_intel/config.py` via `TradeIntelConfig`.

Groups:
- General: `TRADE_INTEL_ENABLED`, storage toggles, JSONL/SQLite paths.
- Attribution: post-trade thresholds (`FAST_INVALIDATION_SECONDS`, slippage/timing thresholds).
- Adaptive sizing: base risk, min/max multipliers, factor weights, block thresholds.
- Smart exits: partial/BE/trailing/time-stop toggles and per-strategy max hold.
- Edge decay: rolling window, minimum sample, disable thresholds, cooldown.
- Segmentation: per-dimension tracking toggles for strategy/instrument/session/regime/setup/spread.
