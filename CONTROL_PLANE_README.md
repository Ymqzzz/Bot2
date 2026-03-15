# Control Plane

This package adds a deterministic coordination layer across regime classification, event state handling, execution intelligence, and portfolio-aware allocation.

## Runtime flow
1. Build market snapshots
2. Build a cycle-level `EventDecision`
3. Build per-instrument `RegimeDecision`
4. Convert strategy plans into allocation/execution candidates
5. Evaluate `ExecutionDecision` per candidate
6. Allocate approved subset with `AllocationDecision`
7. Build `OrderTacticPlan` for approved candidates
8. Persist all outputs via JSONL + SQLite

The control plane uses bounded heuristics and configured thresholds; it is not probabilistically perfect forecasting.
This upgrade adds a deterministic control layer with four outputs per cycle:
- `RegimeDecision`
- `EventDecision`
- `ExecutionDecision`
- `AllocationDecision`

`ControlPlanePipeline` orchestrates regime classification, event-state policying, execution feasibility checks, portfolio-aware allocation, and tactic planning.

Live flow:
1. build event decision
2. classify per-instrument regime
3. evaluate execution feasibility per candidate
4. allocate with concentration/correlation checks
5. persist all outputs in JSONL

This is deterministic policy logic and bounded heuristics; it is not probabilistically perfect forecasting.
