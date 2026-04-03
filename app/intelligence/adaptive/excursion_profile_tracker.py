from __future__ import annotations


class ExcursionProfileTracker:
    def summarize(self, pnl_path: list[float]) -> dict[str, float]:
        if not pnl_path:
            return {"mfe": 0.0, "mae": 0.0, "drift": 0.0}
        mfe = max(pnl_path)
        mae = min(pnl_path)
        drift = pnl_path[-1] - pnl_path[0]
        return {"mfe": float(mfe), "mae": float(mae), "drift": float(drift)}
