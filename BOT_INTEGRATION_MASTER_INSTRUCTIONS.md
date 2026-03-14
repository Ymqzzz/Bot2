# Bot Full Integration Master Instructions (Start-to-Finish)

This document is the **implementation instruction manual** for fully integrating the roadmap into the current bot codebase.

It is written as an execution plan for the agent (or any engineer) to follow sequentially, with explicit file-level changes, testing requirements, rollout controls, and promotion gates.

---

## 0) Mission and non-negotiable constraints

### Primary mission
Build a production-grade FX trading system that can absorb large model complexity while maintaining:

- risk-first capital preservation,
- deterministic decision traceability,
- measurable out-of-sample edge net of costs,
- reversible deployments with hard kill-switch controls.

### Non-negotiables

1. No model is allowed to bypass risk hard-limits.
2. No feature/model is promoted without replay + forward validation.
3. Every trade decision must be reconstructible from logs.
4. Operational reliability beats theoretical alpha.
5. If complexity increases uncertainty faster than performance, complexity is rolled back.

---

## 1) Current-state decomposition and target code map

### Current critical files
- `main.py`: orchestration + data + strategy + risk + execution + command surface.
- `execution_engine.py`: entry type and clip staging plus execution stats.
- `portfolio_risk.py`: exposure/risk caps and portfolio proposal selection.
- `edge_health.py`: strategy edge decay metrics.
- `lifecycle_manager.py`, `world_state.py`, `reporting.py`: lightweight support modules.

### Target module map

Create a new package layout while preserving backwards compatibility during migration:

- `app/config/`
  - `settings.py` (typed config)
  - `validation.py` (required/optional keys)
- `app/data/`
  - `oanda_client.py`
  - `market_data.py` (candles/ticks/spread snapshots)
  - `macro_data.py` (calendar/news/rates)
  - `cache.py` (TTL + freshness guarantees)
- `app/features/`
  - `price_features.py`
  - `microstructure_features.py`
  - `event_features.py`
  - `retail_structure_features.py` (FVG/liquidity sweep/order-block labels)
- `app/models/`
  - `baseline_models.py` (linear/trees)
  - `sequence_models.py` (LSTM/Mamba/S4 as optional providers)
  - `calibration.py`
  - `ensemble.py`
- `app/strategy/`
  - `protocol.py` (StrategyPlugin)
  - `registry.py`
  - `plugins/` (trend/reversion/breakout/carry/event)
- `app/risk/`
  - `trade_risk.py`
  - `portfolio_risk.py` (adapter around existing logic)
  - `tail_risk.py` (VaR/ES/CVaR and dislocation gates)
  - `governors.py` (drawdown/daily loss/throttles)
- `app/execution/`
  - `routing.py` (market/limit/stop policy)
  - `scheduling.py` (TWAP/VWAP/clip policies)
  - `cost_model.py` (shortfall/slippage/adverse selection)
- `app/governance/`
  - `decision_graph.py`
  - `policy_engine.py`
  - `kill_switch.py`
- `app/monitoring/`
  - `events.py` (structured schemas)
  - `metrics.py`
  - `audit.py` (decision lineage)
- `app/research/`
  - `replay_engine.py`
  - `walk_forward.py`
  - `promotion.py`

---

## 2) End-state decision flow (single source of truth)

Implement a strict, deterministic flow:

1. Data snapshot build (market + macro + positions + account).
2. Feature generation (all families with timestamp integrity checks).
3. Strategy plugin candidate generation.
4. Candidate normalization + calibration.
5. Market quality gate (spread/vol/event/dislocation).
6. Risk gate (trade + strategy + cluster + portfolio + session).
7. Edge health and model confidence gate.
8. Execution synthesis (order type + schedule + clip sizes).
9. Policy compliance and audit record creation.
10. Submit order.
11. Post-trade attribution (signal vs execution vs risk outcomes).

Each stage must emit reason-coded events and be replayable.

---

## 3) Implementation phases (full program)

## Phase I — Safety foundation (Weeks 1–3)

### Deliverables
- Typed config extraction and validation.
- Structured event schema and trace ID propagation.
- Hard risk governors (daily loss, drawdown, trade frequency).
- Deterministic decision graph skeleton.

### Required code changes
- Add `app/config/*` and migrate env parsing from `main.py`.
- Add `app/monitoring/events.py` with event DTOs:
  - `signal_emitted`, `signal_rejected`, `risk_blocked`, `order_submitted`, `order_filled`, `strategy_disabled`.
- Wrap existing trade path in `app/governance/decision_graph.py` while calling existing modules.
- Add centralized kill-switch in `app/governance/kill_switch.py`.

### Exit criteria
- Current behavior parity within tolerance.
- Every decision path logged with trace IDs.

## Phase II — Modular strategy and feature layer (Weeks 3–6)

### Deliverables
- Strategy plugin protocol + registry.
- Standard candidate schema.
- Baseline feature stores (trend/reversion/microstructure/event).

### Required code changes
- `app/strategy/protocol.py` with required methods.
- `app/strategy/registry.py` to load/execute plugins.
- Initial plugins migrated from existing logic in `main.py`.
- Add feature pipelines with freshness guards and no-leakage checks.

### Exit criteria
- At least 3 plugin strategies running in production path.
- Candidate generation fully decoupled from order submission.

## Phase III — Risk and execution intelligence (Weeks 6–10)

### Deliverables
- Incremental CVaR and dislocation gating.
- Execution cost model with implementation shortfall decomposition.
- Adaptive order routing with VWAP/TWAP + dynamic clip schedules.

### Required code changes
- Extend existing `portfolio_risk.py` logic through adapter into `app/risk/portfolio_risk.py`.
- Add `app/risk/tail_risk.py` for non-Gaussian/tail/dislocation checks.
- Add `app/execution/cost_model.py` and persist per-instrument/session stats.
- Enhance `execution_engine.py` usage via `app/execution/scheduling.py`.

### Exit criteria
- Measurable slippage reduction or improved fill-quality metrics.
- Portfolio gate blocks correlated/tail-heavy candidates consistently.

## Phase IV — Research and promotion lane (Weeks 10–14)

### Deliverables
- Deterministic replay + walk-forward pipeline.
- Promotion scorecard automation.
- Shadow and canary deployment support.

### Required code changes
- `app/research/replay_engine.py` with bar-by-bar deterministic evaluation.
- `app/research/promotion.py` implementing hard pass/fail criteria.
- Add report generation extensions in `reporting.py` for promotion dashboards.

### Exit criteria
- Every model candidate has reproducible replay artifacts.
- Promotion to production requires all scorecard floors.

## Phase V — Advanced model integration (Weeks 14+)

### Deliverables
- Optional deep sequence model slot (LSTM-attn or Mamba/S4 provider abstraction).
- Synthetic-data robustness harness with fidelity checks.
- Regime-switching and entropy-shift overlays.

### Required code changes
- `app/models/sequence_models.py` as provider interface.
- Synthetic validation utilities in `app/research/`.
- Add regime posterior features to risk throttles.

### Exit criteria
- Advanced models beat baseline net-of-cost and pass robustness checks.
- No increase in operational incident rate.

---

## 4) Detailed workstream instructions (parallel tracks)

## Workstream A — Data contracts

1. Define canonical market snapshot schema (timestamp, instrument, bid/ask, spread, mid, volume).
2. Define macro/event schema with event windows and confidence.
3. Add freshness checks and stale-data reject reasons.
4. Add dataset versioning ID to every replay run.

## Workstream B — Feature governance

1. Tag each feature with source timestamp and transform timestamp.
2. Add leakage tests: no feature can depend on future bars.
3. Add collinearity pruning for redundant indicator sets.
4. Normalize features per instrument/session regime.

## Workstream C — Model governance

1. Standardize model IO:
   - input features,
   - prediction,
   - confidence/uncertainty,
   - model hash/version.
2. Calibration mandatory for probabilistic outputs.
3. Ensemble diversity monitoring:
   - pairwise prediction correlation,
   - model contribution drift.

## Workstream D — Risk/governance

1. Enforce hard risk ceilings independent of model score.
2. Implement regime-weighted sizing and memory-aware throttling.
3. Add dislocation triggers (spread spikes, basis/TAP proxies if available).
4. Global kill-switch with deterministic fallback behavior.

## Workstream E — Execution/TCA

1. Compute implementation shortfall components:
   - decision price -> arrival -> fill -> post-fill drift.
2. Build fill probability surfaces for limit logic.
3. Add order slicing policy by liquidity/volatility/event context.
4. Record adverse selection and crowding proxy metrics.

## Workstream F — Compliance/audit

1. Record full decision lineage:
   - feature snapshot hash,
   - model hash,
   - gate results,
   - final action.
2. Add append-only audit sink and retention policy.
3. Add role separation and restricted override controls.

---

## 5) Testing program (must be implemented with code changes)

### Unit tests
- Feature transforms (math invariants).
- Risk sizing and cap logic.
- Execution schedule generation.

### Property tests
- Exposure constraints always respected.
- Position sizing never exceeds configured bounds.
- Decision graph never emits order when kill-switch active.

### Scenario tests
- High-spread + event risk cases.
- Drawdown breach and recovery mode.
- Correlation spike blocking.

### Replay/regression tests
- Fixed historical windows with frozen data.
- Model promotion scorecard reproducibility.

### Chaos/fault tests
- API timeouts, stale cache, partial data outages.
- Logging/audit sink degradation behavior.

### Acceptance threshold
No release if any critical risk-governance test fails.

---

## 6) Rollout model (start to finish)

1. **Local simulation pass**: all tests + replay baselines pass.
2. **Shadow mode**: live data, no capital, compare decisions.
3. **Canary**: micro-capital with strict lower risk caps.
4. **Progressive scale**: increase capital by objective scorecard milestones.
5. **Full production**: only after sustained stability window.

Rollback triggers:
- scorecard breach,
- risk budget breach,
- execution degradation,
- audit/telemetry gaps.

---

## 7) Scorecard definition for promotion

A candidate module/model must pass all floors:

- Alpha floor: OOS Sharpe/Sortino uplift net of costs.
- Risk floor: CVaR/max-DD not worse than baseline budget.
- Execution floor: shortfall not degraded.
- Robustness floor: stable across sessions/pairs/regimes.
- Complexity floor: latency + ops burden acceptable.
- Governance floor: full traceability and rollback tested.

No floor can be compensated by strength in another category.

---

## 8) Concrete migration instructions for existing files

## `main.py`
- Stepwise carve-out into `app/*` modules.
- Maintain thin orchestrator wrapper only.
- Replace direct logic with service calls.

## `execution_engine.py`
- Keep as low-level utility.
- Move policy composition to `app/execution/*`.
- Add interfaces for session-aware execution stats.

## `portfolio_risk.py`
- Keep mathematical core.
- Add adapter in `app/risk/portfolio_risk.py`.
- Extend with incremental CVaR and dislocation modifiers.

## `edge_health.py`
- Maintain baseline metrics.
- Add Bayesian/posterior extensions in `app/models` or `app/risk`.
- Integrate with strategy enable/disable state machine.

## `reporting.py`
- Extend for replay/promotion scorecards and TCA summaries.
- Include audit coverage metrics.

---

## 9) Full operational runbook

1. Pre-open checks:
   - config validation,
   - data feed health,
   - model version locks,
   - audit sink availability.
2. Live run loop:
   - ingest -> feature -> candidate -> gate -> execute -> attribute.
3. Intraday monitors:
   - risk budget usage,
   - dislocation indicators,
   - execution drift.
4. Incident response:
   - auto-throttle,
   - kill-switch if thresholds exceeded,
   - alert + snapshot state.
5. EOD processing:
   - PnL attribution,
   - model contribution analysis,
   - promotion lane updates,
   - report persistence.

---

## 10) Definition of done (program completion)

The integration is complete only when:

- monolithic critical logic is modularized under `app/*`,
- all decisions are reproducible and audited,
- promotion system controls research-to-production flow,
- risk and execution guardrails operate independently of model outputs,
- replay and forward metrics show sustained net improvement,
- operations can rollback any component rapidly without system failure.

At that point, the bot supports high-complexity quantitative innovation with controlled downside and institutional-grade engineering discipline.
