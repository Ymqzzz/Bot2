from __future__ import annotations

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import NegotiationObjection


class ConflictProtocol:
    """Converts engine disagreements to objections with severity and veto class."""

    def detect(self, *, context: dict) -> list[NegotiationObjection]:
        objections: list[NegotiationObjection] = []
        if float(context.get("microstructure_quality", 0.5)) < 0.35 and context.get("setup_type") == "breakout":
            objections.append(
                NegotiationObjection(
                    source_engine="microstructure",
                    objection_type="fill_quality",
                    severity=clamp(1.0 - float(context.get("microstructure_quality", 0.5))),
                    message="Breakout quality degraded by thin order book.",
                )
            )

        sweep_trap_risk = clamp(float(context.get("sweep_trap_risk", 0.0)))
        if sweep_trap_risk > 0.55:
            objections.append(
                NegotiationObjection(
                    source_engine="surveillance",
                    objection_type="trap_risk",
                    severity=sweep_trap_risk,
                    message="Sweep-to-trap risk elevated.",
                    hard_veto=sweep_trap_risk > 0.8,
                )
            )

        regime_instability = clamp(float(context.get("regime_instability", 0.2)))
        if regime_instability > 0.65:
            objections.append(
                NegotiationObjection(
                    source_engine="regime",
                    objection_type="state_instability",
                    severity=regime_instability,
                    message="Regime transition risk too high.",
                    hard_veto=regime_instability > 0.85,
                )
            )
        return objections
