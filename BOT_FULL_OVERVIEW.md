# Bot System: Full Technical Overview

This repository implements a deterministic, multi-layer FX trading bot platform designed around three principles:

1. **Capital preservation before alpha pursuit**.
2. **Auditable, explainable decisioning** (reason-coded outcomes across subsystems).
3. **Operational resilience under increasing model complexity**.

This document is the single canonical markdown overview for the bot and supersedes the previously split README/config/reason-code/migration notes.

---

## 1) Architectural Intent

At a high level, the bot follows a gated pipeline:

- ingest market/macro/context data,
- generate and score strategy candidates,
- apply intelligence/context moderation,
- route through control-plane policy gates,
- apply trade-intel lifecycle controls,
- enforce risk and execution constraints,
- persist telemetry and decision artifacts for replay, calibration, and diagnostics.

The system is intentionally **deterministic and inspectable**. It does not rely on opaque black-box routing for live approvals.

---

## 2) Layered Runtime Model

### Core runtime and orchestration

The runtime coordinates decision cycles, strategy selection, risk checks, and execution. Historical notes in this repository indicate migration away from monolithic orchestration toward module boundaries (runtime, intelligence, control plane, research core, trade intel).

### Intelligence layer (`app/intelligence`)

Produces a typed market-intelligence snapshot used to shape quality, confidence, and sizing:

- regime context,
- multi-timeframe bias alignment,
- market structure phase labeling,
- liquidity pool/pressure interpretation,
- sweep interpretation,
- event contamination/risk,
- instrument tradability health,
- strategy health throttles,
- cross-asset confirmation/divergence,
- explicit uncertainty scoring,
- setup quality synthesis,
- historical analog support,
- confidence calibration.

Outcome: candidate quality is not just raw signal strength; it is context-adjusted and uncertainty-penalized.

### Control plane (`control_plane`)

A deterministic coordination/governance layer that evaluates live candidate feasibility and concentration risk before final approval.

Primary outputs per cycle:

- `EventDecision`
- `RegimeDecision`
- `ExecutionDecision`
- `AllocationDecision`
- `OrderTacticPlan`

Responsibilities include:

- event lockout/digestion policy,
- per-instrument regime interpretation,
- execution feasibility and slippage/fill constraints,
- correlation/concentration-aware portfolio allocation,
- order tactic overrides (e.g., staging, passive/aggressive routing).

### Trade intelligence (`trade_intel`)

Lifecycle intelligence around each approved trade:

- pre-trade fingerprinting,
- adaptive risk multipliers,
- smart live exit behaviors (partial/BE/trailing/time-stop),
- post-trade attribution,
- segmented performance tracking,
- edge-decay throttling/disable logic.

This keeps position management and post-mortem quality controls tied to measurable behavior rather than static one-size-fits-all rules.

### Research core (`research_core`)

Offline/nearline empirical governance tooling:

- deterministic replay,
- scenario simulation,
- confidence calibration,
- meta-approval quality supervisor.

Purpose: enforce evidence-backed promotion and ongoing quality assurance, not marketing-style “prediction claims”.

---

## 3) Decision Governance and Safety

The platform adopts “hard gates first, optimization second”:

- no trade bypasses risk hard-limits,
- no subsystem promotion without replay/forward-validation,
- all major decisions attach machine-readable reason codes,
- fallback/rollback behavior is explicit when uncertainty or data quality degrades,
- concentration/correlation/event contamination controls can block otherwise attractive entries.

This ensures that complexity increases are bounded by governance rather than allowed to compound hidden fragility.

---

## 4) Explainability Contracts

Subsystems emit structured reason codes (domain-specific constants), covering at least:

- control-plane regime/allocation/event/execution outcomes,
- trade-intel sizing/entry/exit/attribution/edge-decay outcomes,
- research replay/simulation/calibration/meta-approval outcomes.

Reason codes are used for:

- runtime diagnostics,
- replay trace reconstruction,
- post-trade attribution,
- operator confidence and incident review.

---

## 5) Configuration Surface (Environment-Driven)

Configuration is environment-variable driven and grouped by subsystem, with defaults/validation in module config objects.

High-level domains include:

- control-plane toggles, regime thresholds, allocation caps, correlation windows, event lockouts, execution thresholds, tactic behavior;
- trade-intel storage and lifecycle thresholds for sizing/exits/attribution/edge-decay;
- research-core replay/simulation/calibration/meta-approval controls.

Operationally, this allows strict-mode rollouts, feature flags, and incremental promotion without deep code surgery.

---

## 6) Persistence and Audit Trail

Repository notes indicate append-only JSONL and optional SQLite usage for structured observability.

Persisted artifacts may include:

- control-plane decision snapshots,
- order tactic plans,
- trade-intel lifecycle state,
- replay/simulation/calibration reports.

Design goal: any meaningful live decision should be reconstructible later with context and reason hierarchy.

---

## 7) Migration Direction and Technical Debt Posture

The documented roadmap centers on decomposing oversized orchestration into bounded contexts:

- config,
- data access,
- feature engineering,
- strategy family modules,
- risk,
- execution,
- governance,
- monitoring.

This is a deliberate complexity strategy: increase sophistication while reducing hidden coupling and improving testability.

---

## 8) Testing and Quality Expectations

The project expectation is deterministic tests with coverage for both:

- success/approval paths,
- rejection/degraded/failure branches.

Given the decision-heavy nature of the bot, quality depends on verifying policy edges and reason-code correctness, not only happy-path PnL logic.

---

## 9) Practical Mental Model

Think of the bot as a **stack of governors**:

1. strategy proposes opportunities,
2. intelligence scores quality + uncertainty,
3. control plane decides if/when/how allocation is allowed,
4. risk/execution enforce capital and fill constraints,
5. trade intel manages lifecycle adaptation,
6. research core measures and recalibrates what should remain enabled.

Net effect: a system engineered for **controlled adaptability**, where every upgrade is expected to remain auditable and reversible.

---

## 10) Documentation Consolidation Note

This file is intentionally the single markdown overview for the repository and replaces fragmented documentation previously spread across architecture/readme/config/reason-code/migration-note markdown files.
