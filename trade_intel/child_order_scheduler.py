from __future__ import annotations


def schedule_child_orders(total_qty: float, slices: int, urgency: str) -> list[float]:
    qty = max(0.0, float(total_qty))
    n = max(1, int(slices))
    if n == 1:
        return [qty]

    if urgency == "high":
        weights = [1.0 for _ in range(n)]
    elif urgency == "low":
        weights = [i + 1 for i in range(n)]
    else:
        half = n // 2
        weights = [half - abs(i - half) + 1 for i in range(n)]

    s = sum(weights)
    raw = [qty * (w / s) for w in weights]
    rounded = [round(x, 8) for x in raw]
    diff = qty - sum(rounded)
    rounded[-1] = round(rounded[-1] + diff, 8)
    return rounded
