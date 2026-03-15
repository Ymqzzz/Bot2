# Intelligence Layer

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
