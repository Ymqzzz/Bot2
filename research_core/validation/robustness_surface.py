from __future__ import annotations


def robustness_surface(param_grid: dict[str, list[float]], scorer) -> list[tuple[dict[str, float], float]]:
    keys = list(param_grid)
    if not keys:
        return []

    rows: list[tuple[dict[str, float], float]] = []

    def _walk(i: int, current: dict[str, float]) -> None:
        if i == len(keys):
            rows.append((dict(current), float(scorer(current))))
            return
        key = keys[i]
        for v in param_grid[key]:
            current[key] = float(v)
            _walk(i + 1, current)

    _walk(0, {})
    return rows
