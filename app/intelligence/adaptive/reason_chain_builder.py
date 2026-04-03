from __future__ import annotations


class ReasonChainBuilder:
    def build(self, *, supports: list[str], objections: list[str], penalties: dict[str, float]) -> list[str]:
        chain: list[str] = []
        for item in supports:
            chain.append(f"support::{item}")
        for item in objections:
            chain.append(f"oppose::{item}")
        for k, v in penalties.items():
            chain.append(f"penalty::{k}::{v:.3f}")
        return chain
