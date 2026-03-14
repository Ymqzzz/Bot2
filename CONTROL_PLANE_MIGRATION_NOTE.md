# Migration Note

## What changed in `main.py`
- Added long-lived initialization of `ControlPlanePipeline`.
- Added `apply_control_plane(...)` hook to evaluate per-cycle event/regime/execution/allocation decisions against candidate plans.
- Integrated tactic metadata into order type choice inside `execute_trade_plan(...)`.
- Added control-plane diagnostics to replay logs and no-plan decision logs.

## New files
- `control_plane/*` package modules
- `tests/control_plane/*`
- `CONTROL_PLANE_*.md` documentation files

## Storage tables
- `control_regime_decisions`
- `control_event_decisions`
- `control_execution_decisions`
- `control_allocation_decisions`
- `control_portfolio_state_snapshots`
- `control_order_tactic_plans`

## Runtime hooks
- Candidate filtering and approval now pass through `apply_control_plane` before final risk sizing.
- Order tactic metadata is consumed by execution order type selection.
