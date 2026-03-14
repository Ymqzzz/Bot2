from __future__ import annotations

from app.models.schema import SignalCandidate


def candidate_expectancy_proxy(c: SignalCandidate, calibrated_pwin: float) -> float:
    rr_num = abs(c.take_profit - c.entry_price)
    rr_den = max(1e-9, abs(c.entry_price - c.stop_loss))
    rr = rr_num / rr_den
    return calibrated_pwin * rr - (1.0 - calibrated_pwin)


def choose_best_candidate(candidates: list[SignalCandidate], pwin_map: dict[int, float]) -> SignalCandidate | None:
    if not candidates:
        return None
    scored = []
    for idx, c in enumerate(candidates):
        p = float(pwin_map.get(idx, 0.5))
        scored.append((candidate_expectancy_proxy(c, p), c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
