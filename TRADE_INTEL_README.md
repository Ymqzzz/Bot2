# Trade Intel Subsystem

Implements deterministic trade lifecycle intelligence:
- pre-trade fingerprinting + adaptive sizing
- smart live exit policy
- post-trade attribution
- segmented performance + edge-decay throttling/disable

Primary package: `trade_intel/` with modular components for models, classifiers, sizing, exits, attribution, lifecycle, storage, replay, and orchestration.

Lifecycle:
1. `prepare_trade` builds fingerprint, computes sizing decision, and generates exit plan.
2. `on_trade_open/update/partial` tracks live state and drives exit actions.
3. `on_trade_close` finalizes attribution and updates performance/edge health.
