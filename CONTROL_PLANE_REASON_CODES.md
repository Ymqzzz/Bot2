# Control Plane Reason Codes

Reason codes are centralized in `control_plane/reason_codes.py` and grouped by domain:
- Regime (`REGIME_*`)
- Allocation (`ALLOC_*`)
- Event (`EVENT_*`)
- Execution (`EXEC_TACTIC_*`)

They are attached to all major decisions for auditability, persistence, and deterministic replay diagnosis.
