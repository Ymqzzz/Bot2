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
