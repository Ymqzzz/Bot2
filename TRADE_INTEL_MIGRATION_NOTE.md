# Trade Intel Migration Note

## main.py integration
- Startup now initializes `trade_intel_pipeline`.
- Pre-trade flow calls `trade_intel_pipeline.prepare_trade(...)` before risk sizing.
- `risk_approve_and_size(...)` now accepts `trade_prep` and applies adaptive risk multiplier.
- Approved trade metadata carries `trade_intel_id` and exit-plan details.
- Open-trade manager calls `on_trade_update(...)` and executes policy actions (partial/BE/force-exit).
- Close processing calls `on_trade_close(...)` to finalize attribution and performance updates.

## New files
- `trade_intel/*.py`
- `tests/trade_intel/test_trade_intel.py`
- `TRADE_INTEL_README.md`
- `TRADE_INTEL_CONFIG_REFERENCE.md`
- `TRADE_INTEL_REASON_CODES.md`
- `TRADE_INTEL_MIGRATION_NOTE.md`
