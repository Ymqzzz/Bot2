# Intelligence Layer

The intelligence subsystem in `app/intelligence/` produces a deterministic, typed `MarketIntelligenceSnapshot` used by ranking, confidence moderation, sizing, governance metadata, and audit replay.

## Engine Roles
- `regime.py`: regime label + vectorized context scores.
- `mtf_bias.py`: multi-timeframe alignment/conflict decomposition.
- `structure.py`: sequence-aware phase model (`compression_*`, `reclaim_phase`, `expansion_leg`, etc.) plus messiness and continuation/reversal quality.
- `liquidity.py`: ranked liquidity pool map with significance, visibility, cluster density, target likelihood, and directional pressure.
- `sweep.py`: breach + response + follow-through interpretation (`external_sweep_rejection`, `external_sweep_acceptance`, ambiguous/failed states).
- `event_risk.py`: event contamination model.
- `instrument_health.py`: tradability health state and penalties.
- `strategy_health.py`: sample-aware health score, throttles, rank/size penalties, optional disable recommendation.
- `cross_asset.py`: macro confirmation/divergence context.
- `uncertainty.py`: explicit uncertainty model from conflicting/insufficient evidence (not `1-confidence`).
- `trade_quality.py`: central setup synthesis with decomposed contributions, context penalties, and size hints.
- `analog.py`: weighted historical analog retrieval with explainable similarity dimensions.
- `calibrator.py`: confidence moderation that combines uncertainty and analog support.

## Score Ranges and Meanings
All scalar scores are bounded to `[0.0, 1.0]`.
- Higher `trade_quality.quality_score` = cleaner + more aligned + more tradable setup.
- Higher `uncertainty.uncertainty_score` = more conflicting/sparse context; reduces confidence/rank/size.
- Higher `liquidity.pressure_score` = stronger likelihood that meaningful pools are being targeted.
- Higher `analog.analog_confidence` = stronger confidence in historical comparability.

## Orchestration Order
`orchestrator.py` now runs:
1. regime/MTF/structure/liquidity/sweep/event/instrument/strategy/cross-asset,
2. preliminary uncertainty,
3. trade quality synthesis,
4. analog retrieval,
5. final uncertainty + trade quality refresh,
6. confidence calibration.

## Runtime Integration
`app/runtime/upgraded_bot.py` uses intelligence outputs to:
- refine candidate score (quality + uncertainty penalties),
- feed confidence calibration,
- apply quality/uncertainty/strategy-health multipliers in sizing,
- emit intelligence lineage into governance decision metadata and audit snapshots.

## Analog Similarity Heuristic
`analog.py` applies deterministic weighted similarity across regime, alignment, structure phase, liquidity context, sweep type, spread burden, event contamination, instrument health, and quality bucket. Top-N matches produce expectancy/win-rate/payoff/MAE/MFE summaries with sparse-history flags.

## Safe Extension Pattern
1. add typed output fields in `models.py` (with defaults for backward compatibility),
2. keep engine deterministic and bounded,
3. emit machine-readable `Evidence` rationale,
4. wire dependencies in `orchestrator.py`,
5. integrate consumers (rank/calibrate/size/audit),
6. add scenario tests before rollout.
The intelligence subsystem in `app/intelligence/` produces a deterministic, replayable `MarketIntelligenceSnapshot` used directly by ranking, confidence moderation, sizing, and audit metadata.

## Engine Roles (Upgraded)
- `regime.py`: classifies market regime and instability vectors.
- `mtf_bias.py`: multi-timeframe alignment/conflict modeling.
- `structure.py`: sequence-aware structural phase engine (`compression_*`, `failed_continuation`, `reclaim_phase`, `expansion_leg`, etc.).
- `liquidity.py`: significance-ranked liquidity pools (distance and importance separated).
- `sweep.py`: breach + response + follow-through interpretation (`*_rejection`, `*_acceptance`, `ambiguous_breach`, etc.).
- `event_risk.py`: event contamination and cooldown effects.
- `instrument_health.py`: tradability health and penalty multipliers.
- `strategy_health.py`: sample-aware strategy health, throttles, rank/size penalties, disable recommendations.
- `cross_asset.py`: cross-asset confirmation/divergence context.
- `trade_quality.py`: central synthesis layer (cleanliness, alignment, context penalties, execution burden, quality factors).
- `analog.py`: weighted historical analog retrieval with expectancy/win-rate/MAE/MFE summaries.
- `uncertainty.py`: explicit uncertainty model (not `1-confidence`) built from conflicting/insufficient evidence.
- `calibrator.py`: combines uncertainty + analog evidence to moderate confidence.

## Score Ranges and Meaning
All major scores are bounded to `[0, 1]`.
- Higher `trade_quality_score` means cleaner/aligned/actionable setups.
- Higher `uncertainty_score` means more conflicting or insufficient evidence.
- `size_multiplier_hint` and `size_penalty_multiplier` are applied downstream in sizing.
- `ranking_penalty` is applied in candidate discrimination.

## Runtime Integration Points
`app/runtime/upgraded_bot.py` now:
1. builds per-candidate snapshots,
2. applies quality/uncertainty modifiers in candidate selection,
3. calibrates confidence,
4. applies quality/uncertainty/strategy multipliers in position sizing,
5. emits full intelligence lineage to decisions and audit payloads.

## Analog Similarity Heuristic
`analog.py` uses deterministic weighted similarity across regime, alignment, structure phase, liquidity pressure, sweep type, spread burden, event contamination, strategy family, and quality bucket. Top matches are aggregated into expectancy/win-rate/payoff/MAE/MFE diagnostics with explicit sparse-history flags.

## Extending Safely
1. Add typed fields in `models.py` (schema versioned).
2. Keep scores bounded and rationale machine-readable.
3. Wire engine in `orchestrator.py` once (no duplicate intelligence paths).
4. Ensure downstream consumers (ranker/size/audit) consume new fields.
5. Add deterministic tests for both nominal and degraded-data scenarios.
