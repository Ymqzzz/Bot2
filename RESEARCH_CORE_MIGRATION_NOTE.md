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
