# Research Core Migration Note

## Runtime changes
- `main.py` now initializes `research_core` pipeline at startup when enabled.
- Meta-approval helper functions were added for live candidate supervision.
- Research mode now supports subcommands: `replay`, `simulate`, `calibrate`, `report`.

## New storage
- JSONL artifacts under `REPORTS_OUTPUT_DIR`.
- Optional SQLite tables are created by `research_core.storage.ResearchStorage`.

## New hooks
- Calibration refresh hook for startup/research paths.
- Candidate-level meta-approval hook for decision gating.

## Deprecation notice
- The legacy direct orchestration path in `main.py` is now deprecated. Research-core meta approval should run through the coordinator-driven lifecycle in `app/runtime/engine.py`.
