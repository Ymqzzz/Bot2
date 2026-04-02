from __future__ import annotations


def early_stop(validation_scores: list[float], patience: int) -> bool:
    if len(validation_scores) <= patience:
        return False
    recent = validation_scores[-patience:]
    return max(recent) < max(validation_scores[:-patience])
