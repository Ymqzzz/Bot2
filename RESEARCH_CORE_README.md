# Research Core

`research_core` adds deterministic replay, scenario simulation, segmented confidence calibration, and a rule-based meta-approval supervisor.

## Components
- Replay lab: time-ordered reconstruction with divergence flags.
- Simulation framework: isolated scenario overrides against baseline.
- Confidence calibration: segmented snapshots with fallback hierarchy.
- Meta-approval layer: approve/downsize/delay/reject with reason codes.

## Truthful scope
This package does **not** claim market prediction. It adds auditability, empirical calibration, and supervised quality control.
