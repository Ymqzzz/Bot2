from __future__ import annotations

from app.intelligence.base import clamp


class TradePathShapeModel:
    def smoothness(self, pnl_path: list[float]) -> float:
        if len(pnl_path) < 3:
            return 0.5
        diffs = [pnl_path[i] - pnl_path[i - 1] for i in range(1, len(pnl_path))]
        sign_flips = sum(1 for i in range(1, len(diffs)) if diffs[i] * diffs[i - 1] < 0)
        chaotic = sign_flips / max(1, len(diffs) - 1)
        return clamp(1.0 - chaotic)

    def excursion_balance(self, mfe: float, mae: float) -> float:
        denom = max(abs(mfe) + abs(mae), 1e-9)
        return clamp((mfe - abs(mae)) / denom * 0.5 + 0.5)
