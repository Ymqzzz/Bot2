from __future__ import annotations


def sharpe_by_regime(returns: list[tuple[str, float]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for regime, value in returns:
        buckets.setdefault(regime, []).append(value)

    out: dict[str, float] = {}
    for regime, vals in buckets.items():
        if len(vals) < 2:
            out[regime] = 0.0
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        out[regime] = 0.0 if var <= 0 else mean / (var ** 0.5)
    return out
