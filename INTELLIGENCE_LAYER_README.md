# Intelligence Layer

This repository now includes a modular intelligence subsystem in `app/intelligence/` that transforms feature vectors + market context into a typed `MarketIntelligenceSnapshot`.

## Engines
- `regime.py`: composite regime classification with score vector and explainable weighted evidence.
- `mtf_bias.py`: 4H/1H/15M/5M/1M bias extraction, alignment/conflict scoring.
- `structure.py`: BOS/CHoCH/failed-breakout and structural cleanliness/displacement modeling.
- `liquidity.py`: prior-day/session/round-number liquidity mapping with zone significance.
- `sweep.py`: sweep rejection vs continuation interpretation using post-breach behavior.
- `event_risk.py`: severity/relevance/proximity contamination model.
- `instrument_health.py`: tradability health scoring + penalty multiplier.
- `strategy_health.py`: dynamic per-strategy context-aware health with low-sample handling.
- `cross_asset.py`: macro confirmation/contradiction context with graceful missing-feed behavior.
- `trade_quality.py`: decomposable final quality score and size multiplier suggestion.
- `analog.py`: nearest-neighbor historical analog state.
- `calibrator.py`: confidence moderation/boosting over raw signal confidence.

## Orchestration
`orchestrator.py` executes engines in dependency order and emits a unified `MarketIntelligenceSnapshot` carrying:
- categorical labels
- bounded scores
- confidence
- machine-readable rationale evidence
- schema version metadata

## Runtime Integration
`app/runtime/upgraded_bot.py` now:
1. builds intelligence snapshots per instrument cycle,
2. calibrates candidate confidence with the intelligence layer,
3. injects intelligence payloads into decision outputs,
4. persists full intelligence snapshots into the audit sink for replayability.

## Extensibility
To add a new engine:
1. define typed output in `models.py`,
2. implement deterministic logic in a new module,
3. wire dependencies in `orchestrator.py`,
4. include rationale evidence and bounded scores,
5. add targeted tests.
