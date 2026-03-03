from __future__ import annotations


def normalize_quota_mode(mode: str) -> str:
    if mode in {"normal", "expand_breadth", "scalp_mode"}:
        return mode
    return "normal"
