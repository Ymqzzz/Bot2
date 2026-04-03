# Production-Grade Codex Prompt: 2–4k LOC Trading Intelligence Upgrade

You are upgrading an existing multi-layer trading architecture. Implement **seven major subsystems** with explicit contracts, reason codes, telemetry, and tests. Keep all behavior deterministic and auditable.

## Hard Constraints

1. Add **2,000–4,000 lines of meaningful code** (no filler, no dead code).
2. Every new subsystem must include:
   - typed models (dataclasses or Pydantic)
   - explicit input/output contracts
   - structured reason codes
   - event-driven telemetry hooks
   - unit tests that cover success + rejection/failure branches
3. Avoid black-box magic. Favor explainable, inspectable logic.
4. Preserve existing module boundaries (decision, regime, weighting, risk, execution, surveillance).
5. Any trade approval must include machine-readable justification.

---

## Deliverable 1 — Probabilistic Meta-Decision Layer

Create a new decision layer that converts upstream signals into a **trade distribution** object and a final approval decision.

### Required output schema
- expected_return
- expected_downside
- expected_holding_time
- fill_adjusted_alpha
- uncertainty_interval
- approval_status (`approved`, `declined`, `degraded_approved`)
- decline_reason_hierarchy (ordered list)

### Required logic
Trade is allowed only if all pass:
- `ev_after_costs > min_edge(context)`
- `expected_downside < downside_limit(context)`
- `uncertainty < uncertainty_ceiling(context)`
- `execution_quality_estimate > min_exec_quality`
- `regime_transition_risk < transition_risk_limit`

### Required files
- `trade_intel/decision_engine.py`
- `trade_intel/trade_distribution.py`
- `trade_intel/confidence_calibration.py`
- `trade_intel/edge_threshold_model.py`
- `trade_intel/decision_reason_tree.py`

### Required depth
- Bayesian confidence adjustment
- confidence decay by staleness
- disagreement penalty across engines
- transition-risk penalty when regime confidence weakens
- dynamic min-edge thresholds by instrument + session

---

## Deliverable 2 — Regime Transition Modeling

Extend regime logic from point labels to transition-aware state modeling.

### Required output schema
- current_regime
- regime_confidence
- transition_probability_matrix
- expected_state_duration
- instability_score
- safety_flags (e.g., `unsafe_for_trend_following`)

### Required files
- `trade_intel/regime_transition_model.py`
- `trade_intel/state_persistence_estimator.py`
- `trade_intel/regime_conflict_resolver.py`
- `trade_intel/regime_instability_penalty.py`

### Required behavior
- Track rolling regime history
- estimate persistence + switching intensity
- derate trend-concentrated signals during instability
- reduce max position size under transition stress

---

## Deliverable 3 — Signal Orthogonalization + Redundancy Control

Build explicit anti-double-counting logic so correlated engines do not masquerade as independent confirmation.

### Required files
- `trade_intel/signal_graph.py`
- `trade_intel/feature_overlap_matrix.py`
- `trade_intel/rolling_correlation_penalty.py`
- `trade_intel/signal_cluster_allocator.py`
- `trade_intel/orthogonal_signal_score.py`

### Required behavior
- compute rolling pairwise correlations
- cluster redundant signals
- cap effective vote per correlated cluster
- apply orthogonalization penalty in final confidence
- support engine-level and feature-level overlap
- support regime-conditional dependency profiles

---

## Deliverable 4 — Live Attribution + Adaptive Weighting

Build a post-trade attribution loop that continuously updates trust and weights.

### Required files
- `trade_intel/trade_attribution_engine.py`
- `trade_intel/engine_scorecard.py`
- `trade_intel/adaptive_weight_updater.py`
- `trade_intel/performance_decay_model.py`
- `trade_intel/contextual_weight_memory.py`

### Required metrics
- supporting vs opposing engine contributions
- realized-vs-predicted edge error
- confidence calibration error
- regime-fit accuracy
- execution impact attribution
- risk-saved-overexposure attribution

### Required behavior
- exponentially weighted memory
- regime/session/instrument-specific trust
- classify outcomes: good, bad, lucky, unlucky
- update weighting policy safely (bounded update steps)

---

## Deliverable 5 — Execution Simulator + Microstructure Cost Model

Upgrade execution from order-type toggle to pre-trade cost-aware simulation.

### Required files
- `trade_intel/execution_simulator.py`
- `trade_intel/fill_probability_model.py`
- `trade_intel/slippage_estimator.py`
- `trade_intel/queue_position_tracker.py`
- `trade_intel/adverse_selection_guard.py`
- `trade_intel/child_order_scheduler.py`

### Required behavior
- estimate spread/slippage/latency/partial-fill risk
- estimate adverse selection and queue decay
- market vs limit vs post-only selection
- session-aware spread + vol-adjusted slippage models
- child-order slicing and replay simulation
- publish execution scorecard after each fill

### Required formula wiring
`expected_alpha_after_costs = raw_alpha - spread_cost - slippage_cost - toxicity_penalty`

---

## Deliverable 6 — Research-Grade Validation Package

Add robust validation designed to reduce leakage and overfitting risk.

### Required files
- `research_core/validation/purged_split.py`
- `research_core/validation/embargo.py`
- `research_core/validation/walk_forward_runner.py`
- `research_core/validation/regime_segment_report.py`
- `research_core/validation/ablation_runner.py`
- `research_core/validation/robustness_surface.py`

### Required behavior
- purged walk-forward splits
- embargo logic
- regime-segmented replay reports
- transaction-cost-inclusive validation
- ablation analysis across engine families
- stress scenario replay

### Required outputs
- Sharpe by regime
- expectancy by session
- max drawdown by state
- feature importance drift
- post-deployment edge decay
- false-positive cluster analysis

---

## Deliverable 7 — Failure Safety + Self-Diagnosis

Add continuous health and degraded-mode infrastructure.

### Required files
- `trade_intel/health_monitor.py`
- `trade_intel/feature_integrity_checker.py`
- `trade_intel/clock_sync_guard.py`
- `trade_intel/data_freshness_monitor.py`
- `trade_intel/live_vs_backtest_drift_detector.py`
- `trade_intel/circuit_breaker.py`
- `trade_intel/degraded_mode_controller.py`

### Required behavior
- detect stale/lagging data
- detect NaN or out-of-domain feature spikes
- detect module health failures and timing drift
- detect live-vs-expected divergence
- degrade gracefully rather than crash
- disable dependent modules automatically
- reduce risk budgets in degraded mode
- escalate to manual review with reason hierarchy

---

## Integration Requirements

1. Wire new subsystems into the existing orchestration path.
2. Add or extend shared reason-code registries.
3. Emit structured telemetry events at every decision boundary.
4. Add integration tests for:
   - full approval path
   - each major rejection path
   - degraded mode fallback path
   - stale data + transition instability + high cost scenario
5. Add concise architecture docs explaining contracts and sequence.

---

## Non-Goals / Anti-Patterns

- Do not inflate complexity with extra indicators.
- Do not silently mutate weights without audit logs.
- Do not hide decisions behind opaque scalar “confidence.”
- Do not pass incomplete contexts between layers.
- Do not ship without tests and telemetry.

---

## Acceptance Checklist

- [ ] 2k–4k LOC of meaningful, reviewable additions
- [ ] Seven subsystems implemented and wired
- [ ] Typed contracts + reason codes + telemetry for all
- [ ] Unit tests + integration tests for allow/deny/degraded flows
- [ ] Validation package supports purged + embargoed evaluation
- [ ] Execution simulation influences final approval decisions
- [ ] Docs summarize architecture, assumptions, and limitations
