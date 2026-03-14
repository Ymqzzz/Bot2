# Control Plane Migration Note

## Main runtime changes
- Added control plane imports/config init in `main.py`.
- Added `control_plane_select_plan()` hook before legacy strategy selection.
- `trade_once()` now attempts control-plane selection/allocation first and falls back to legacy router.
- Selected plan order type can now be overridden by control-plane execution tactic.
- Replay logs now include serialized control-plane snapshot.

## New files
- `control_plane/*` modules for models, config, regime/event/execution/allocator/tactics/storage/replay/pipeline.
- `tests/control_plane/*`
- `CONTROL_PLANE_*.md` docs.

## Storage additions
- JSONL append-only logs under `control_plane_logs/` for regime/event/execution/allocation/portfolio/tactic outputs.
- Optional SQLite table creation in `control_plane/storage.py`.

## Runtime hooks
- Event + regime + execution + allocator + tactic decisions are orchestrated by `ControlPlanePipeline`.
