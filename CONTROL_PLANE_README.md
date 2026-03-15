# Control Plane

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
