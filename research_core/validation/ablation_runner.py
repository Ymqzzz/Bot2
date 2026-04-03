from __future__ import annotations

from typing import Callable


def run_ablation(engines: list[str], evaluator: Callable[[list[str]], float]) -> dict[str, float]:
    baseline = evaluator(engines)
    out: dict[str, float] = {"baseline": baseline}
    for engine in engines:
        kept = [e for e in engines if e != engine]
        out[f"drop_{engine}"] = evaluator(kept)
    return out
