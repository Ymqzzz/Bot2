# Control Plane Config Reference

Configuration is read from environment variables in `control_plane/config.py` and validated in `ControlPlaneConfig.validate()`.

## Domains
- General toggles (`CONTROL_PLANE_ENABLED`, `CONTROL_PLANE_STRICT_MODE`)
- Regime engine lookbacks/thresholds
- Allocation caps and score weights
- Correlation windows
- Event lockout and digestion windows
- Execution intelligence thresholds
- Order tactic controls and staging

See `control_plane/config.py` for the complete list and defaults.
